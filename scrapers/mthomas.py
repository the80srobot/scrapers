import pathlib
import lxml.html
from lxml.cssselect import CSSSelector
from typing import List, Dict, Any, Union
import requests
import sys

SAFARI_UAGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"


def get_player_page(
    id: str, elggperm_token: str, asp_session_id: str
) -> requests.Response:
    url = f"https://library.michelthomas.com/{id}"
    resp = requests.get(
        url=url,
        headers={
            "User-Agent": SAFARI_UAGENT,
            "Accept": r"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        cookies={
            "elggperm": elggperm_token,
            "ASP.NET_SessionId": asp_session_id,
        },
    )

    resp.raise_for_status()

    if b"<items>" not in resp.content:
        raise RuntimeError("player page does not have <items>")

    return resp


def player_tracks(doc: lxml.etree.Element) -> List[Dict[str, str]]:
    sel = CSSSelector("items")
    items = sel(doc)[0]
    return [
        {
            "name": item.get("name"),
            "url": item.get("downloadurl"),
            # The checksum is either bogus or uses some exotic algorithm.
            # (It's not md5, sha1, sha256, crc32 or adler32.)
            # "md5": item.get("checksum"),
        }
        for item in items
    ]


def doc_title(doc: lxml.etree.Element) -> str:
    try:
        return [e for e in doc[0] if e.tag == "title"][0].text.strip()
    except IndexError:
        return "-"


def get_playlist(
    id: str, elggperm_token: str, asp_session_id: str
) -> Dict[str, Union[str, List[Dict[str, str]]]]:
    sys.stderr.write(f"Trying to resolve tracklist with ID {id}...\n")
    with get_player_page(
        id=id, elggperm_token=elggperm_token, asp_session_id=asp_session_id
    ) as resp:
        doc = lxml.html.document_fromstring(resp.content)
        items = player_tracks(doc)
        title = doc_title(doc)

        return dict(
            title=title,
            tracks=items,
        )


def scrape_playlist(pl: Dict[str, Union[str, List[Dict[str, str]]]], out_path: str):
    out_dir = pathlib.Path(out_path) / pl["title"]
    out_dir.mkdir(parents=True, exist_ok=True)
    sys.stderr.write(f"Getting tracklist {pl['title']} ({len(pl['tracks'])} tracks)\n")
    i = 0
    for track in pl["tracks"]:
        i += 1
        sys.stderr.write(f"\tGetting track {i}/{len(pl['tracks'])} - {track['name']}...\n")
        file_path = out_dir / track["name"]

        if file_path.is_file():
            sys.stderr.write("\t\t[EXISTS]\n")
            # Can't check the checksum, because it's bogus.
            continue

        with requests.get(url=track["url"], stream=True) as resp:
            resp.raise_for_status()                
            with open(file_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            sys.stderr.write("\t\t[OK]\n")
