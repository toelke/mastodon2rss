"""Read home timeline into RSS"""
from pathlib import Path
import logging
import base64
from io import BytesIO
from functools import lru_cache
import os

import cherrypy
from feedgen.feed import FeedGenerator
import requests
from PIL import Image
from yarl import URL

from mastodon import Mastodon

logging.basicConfig(level=logging.DEBUG)

SCOPES = ["read:statuses", "read:accounts"]

OWN_MASTODON_INSTANCE = os.environ['OWN_MASTODON_INSTANCE']
PUBLIC_URL = URL(os.environ['PUBLIC_URL'])


def get_smaller_image(url):
    return str(
        PUBLIC_URL / "image" % {"id": base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8')}
    )


@lru_cache(maxsize=10000)
def small_image(id):
    response = requests.get(base64.urlsafe_b64decode(id))
    img = Image.open(BytesIO(response.content))
    img.thumbnail((32, 32))
    buffer = BytesIO()
    img.save(buffer, "PNG")
    return buffer.getvalue()


def render_post(post):
    yield from (
        "<div>",
        f"""<img src="{get_smaller_image(post['account']['avatar'])}"/>""",
        f"""<a href="{post.get("uri")}">{post['account']['username']}</a>"""
        if post["uri"]
        else f"""{post['account']['username']}""",
        "</div>",
    )
    yield from ("<div>", post.get("content"), "</div>")
    for ma in post["media_attachments"]:
        if ma["type"] == "image":
            yield from (
                "<div>",
                f'<img src="{ma["url"]}"/>',
                "</div>",
            )
        elif ma["type"] in ('video', 'gifv'):
            yield from ("<div>", f'<video src="{ma["url"]}"/>', "</div>")
        else:
            yield from ("<div>", ma["type"], "</div>")
    if post['card'] is not None:
        if post['card']['type'] == "link":
            img = (
                f"""<div><img src="{get_smaller_image(post['card']['image'])}"/></div>"""
                if post['card']['image'] is not None
                else ""
            )
            yield f"""<a href="{post['card']['url']}" target="_blank" rel="noopener noreferrer">{img}<div><strong>{post['card']['title']}</strong></div></a>"""
    if post["reblog"] is not None:
        yield from ("""<div style="margin-left: 40px">""", *render_post(post["reblog"]), "</div>")


def get_app():
    """Return client_id, secret, api_base_url, maybe loaded from fs, maybe newly created"""
    app = Path('./app')
    if not app.exists():
        api_base_url = f'https://{OWN_MASTODON_INSTANCE}'
        client_id, client_secret = Mastodon.create_app(
            'mastodon2rss',
            api_base_url=api_base_url,
            to_file=app,
            scopes=SCOPES,
            redirect_uris=[str(PUBLIC_URL / 'login_token')],
        )
    else:
        client_id, client_secret, api_base_url, _ = (
            x.strip() for x in app.open('r', encoding='utf-8').readlines()
        )

    return client_id, client_secret, api_base_url


class MastodonFeed:
    def _try_login(self):
        creds = Path('./creds')

        if creds.exists():
            self._mastodon = Mastodon(access_token=creds)
            self.logged_in = True

    def __init__(self):
        client_id, client_secret, api_base_url = get_app()
        self._mastodon = Mastodon(
            client_id=client_id, client_secret=client_secret, api_base_url=api_base_url
        )
        self.logged_in = False
        self._try_login()

    @cherrypy.expose
    def image(self, id):
        cherrypy.response.headers['Content-Type'] = "image/png"

        return small_image(id)

    @cherrypy.expose
    def index(self):
        if self.logged_in:
            yield "<html><body>"
            for post in self._mastodon.timeline():
                yield "<div>"
                yield from render_post(post)
                yield "</div>"
            yield "</body></html>"
            return

        raise cherrypy.HTTPRedirect(
            self._mastodon.auth_request_url(scopes=SCOPES, redirect_uris=str(PUBLIC_URL / 'login_token'))
        )

    @cherrypy.expose
    def feed(self):
        cherrypy.response.headers['Content-Type'] = 'application/atom+xml'
        if self.logged_in:
            fg = FeedGenerator()
            fg.title('Mastodon home Feed')
            fg.language('en')
            fg.id(f'https://{OWN_MASTODON_INSTANCE}/')
            for post in self._mastodon.timeline():
                fe = fg.add_entry()
                fe.id(post['uri'])
                if post['url'] is not None:
                    fe.link(href=post['url'])
                else:
                    if post['reblog']['url'] is not None:
                        fe.link(href=post['reblog']['url'])
                fe.title(f"Post by {post['account']['username']} at {post['created_at']}")
                fe.content(content="".join(render_post(post)), type="CDATA")

            return fg.atom_str()

        raise cherrypy.HTTPError("403" "login first")

    @cherrypy.expose
    def login_token(self, code, **_):
        creds = Path('./creds')
        self._mastodon.log_in(
            code=code,
            to_file=creds,
            scopes=SCOPES,
            redirect_uri=str(PUBLIC_URL / 'login_token'),
        )
        self.logged_in = True
        raise cherrypy.HTTPRedirect(str(PUBLIC_URL))


if __name__ == "__main__":
    cherrypy.config.update({'server.socket_host': '0.0.0.0', 'server.socket_port': 12345})
    cherrypy.quickstart(MastodonFeed())
