# mastodon2rss
Serve your mastodon home feed to RSS

## How

### Very quick:
```
docker run -p 8080:12345 -e OWN_MASTODON_INSTANCE=your.social -e  PUBLIC_URL=https://where.you.make.this/available -v mastodon2rss:/data toelke158/mastodon2rss
```

### A bit slower:

Run the Docker image `toelke158/mastodon2rss` anywhere. Point a (password protected!) reverse proxy at port `12345` of the running container. Put the external name (and path) of your reverse proxy configuration into the environment variable `PUBLIC_URL`. Set the environment variable `OWN_MASTODON_INSTANCE` to your mastodon instance.

You can then visit `PUBLIC_URL` to handle the login to Mastodon. Then you can put `PUBLIC_URL/rss` into your RSS reader of choice.

## Why

I do not like infinitely scrolling web pages. But I like Mastodon. You can read the posts of any Mastodon user as an RSS feed under `https://instance/user/rss` -- but that feed does not contain boosts. Moreover, it removes the interaction of following people.

So I built this to translate my home timeline to RSS.
