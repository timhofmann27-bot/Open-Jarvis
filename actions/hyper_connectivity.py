"""
JARVIS Hyper-Connectivity: Spotify, GitHub und weitere Dienste.
"""

import json
import os
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _get_api_key() -> dict:
    return json.loads((BASE_DIR / "config" / "api_keys.json").read_text(encoding="utf-8"))


# ── Spotify ──────────────────────────────────────────────────────────────────

def _spotify_client():
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    keys = _get_api_key()
    cid = keys.get("spotify_client_id", "")
    secret = keys.get("spotify_client_secret", "")
    redirect = keys.get("spotify_redirect_uri", "http://localhost:8888/callback")
    if not cid or not secret:
        return None, "Spotify nicht konfiguriert. Setze spotify_client_id + spotify_client_secret in api_keys.json"
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=cid, client_secret=secret,
            redirect_uri=redirect,
            scope="user-read-playback-state,user-modify-playback-state,user-read-currently-playing,playlist-read-private",
            cache_path=str(BASE_DIR / "config" / ".spotify_cache"),
        ))
        return sp, None
    except Exception as e:
        return None, f"Spotify Auth Fehler: {e}"


def spotify_action(action: str, query: str = "", playlist_id: str = "") -> str:
    sp, err = _spotify_client()
    if err:
        return err

    try:
        if action == "current":
            track = sp.current_user_playing_track()
            if track and track.get("item"):
                t = track["item"]
                artists = ", ".join(a["name"] for a in t.get("artists", []))
                return f"Spielt gerade: {t['name']} von {artists} ({track['device']['name'] if track.get('device') else '?'})"
            return "Nichts spielt gerade."

        elif action == "play":
            sp.start_playback()
            return "Playback gestartet."

        elif action == "pause":
            sp.pause_playback()
            return "Playback pausiert."

        elif action == "next":
            sp.next_track()
            return "Nächster Titel."

        elif action == "previous":
            sp.previous_track()
            return "Vorheriger Titel."

        elif action == "search":
            if not query:
                return "Suchbegriff angeben."
            results = sp.search(q=query, limit=5, type="track")
            tracks = results.get("tracks", {}).get("items", [])
            if not tracks:
                return f"Nichts gefunden für '{query}'."
            lines = ["Suchergebnisse:"]
            for t in tracks:
                artists = ", ".join(a["name"] for a in t.get("artists", []))
                lines.append(f"  {t['name']} – {artists} ({t['album']['name']})")
            return "\n".join(lines[:6])

        elif action == "play_track":
            if not query:
                return "Titelnamen angeben."
            results = sp.search(q=query, limit=1, type="track")
            tracks = results.get("tracks", {}).get("items", [])
            if not tracks:
                return f"'{query}' nicht gefunden."
            sp.start_playback(uris=[tracks[0]["uri"]])
            return f"Spiele: {tracks[0]['name']}"

        elif action == "playlist":
            playlists = sp.current_user_playlists(limit=10)
            items = playlists.get("items", [])
            if not items:
                return "Keine Playlists gefunden."
            lines = ["Deine Playlists:"]
            for p in items:
                lines.append(f"  {p['name']} ({p['tracks']['total']} Tracks)")
            return "\n".join(lines)

        elif action == "devices":
            devices = sp.devices()
            devs = devices.get("devices", [])
            if not devs:
                return "Keine aktiven Geräte."
            lines = ["Verfügbare Geräte:"]
            for d in devs:
                active = " (aktiv)" if d.get("is_active") else ""
                lines.append(f"  {d['name']}{active}")
            return "\n".join(lines)

        else:
            return f"Unbekannte Spotify-Aktion: {action}"

    except Exception as e:
        return f"Spotify Fehler: {e}"


# ── GitHub ───────────────────────────────────────────────────────────────────

def _github_client():
    from github import Github
    keys = _get_api_key()
    token = keys.get("github_token", "")
    if not token:
        return None, "GitHub nicht konfiguriert. Setze github_token in api_keys.json"
    try:
        g = Github(token)
        user = g.get_user()
        user.login  # test connection
        return g, None
    except Exception as e:
        return None, f"GitHub Fehler: {e}"


def github_action(action: str, repo_name: str = "", issue_title: str = "", issue_body: str = "", pr_number: int = 0) -> str:
    g, err = _github_client()
    if err:
        return err

    try:
        if action == "user":
            user = g.get_user()
            return f"Eingeloggt als {user.login} ({user.name or '?'}) – {user.public_repos} Repos, {user.followers} Follower"

        elif action == "repos":
            user = g.get_user()
            repos = list(user.get_repos())[:15]
            if not repos:
                return "Keine Repos gefunden."
            lines = ["Repositories:"]
            for r in repos:
                lines.append(f"  {r.full_name} ({r.language or '?'}, {r.stargazers_count} Sterne)")
            return "\n".join(lines)

        elif action == "issues":
            if not repo_name:
                return "Bitte Repo angeben (z.B. 'user/repo')."
            repo = g.get_repo(repo_name)
            issues = list(repo.get_issues(state="open"))[:10]
            if not issues:
                return f"Keine offenen Issues in {repo_name}."
            lines = [f"Issues in {repo_name}:"]
            for i in issues:
                lines.append(f"  #{i.number} {i.title} ({'open' if i.state == 'open' else 'closed'})")
            return "\n".join(lines)

        elif action == "create_issue":
            if not repo_name or not issue_title:
                return "Bitte Repo und issue_title angeben."
            repo = g.get_repo(repo_name)
            issue = repo.create_issue(title=issue_title, body=issue_body or "")
            return f"Issue #{issue.number} erstellt: {issue.title}"

        elif action == "prs":
            if not repo_name:
                return "Bitte Repo angeben."
            repo = g.get_repo(repo_name)
            prs = list(repo.get_pulls(state="open"))[:10]
            if not prs:
                return f"Keine offenen PRs in {repo_name}."
            lines = [f"Pull Requests in {repo_name}:"]
            for pr in prs:
                lines.append(f"  #{pr.number} {pr.title} ({pr.user.login})")
            return "\n".join(lines)

        elif action == "commits":
            if not repo_name:
                return "Bitte Repo angeben."
            repo = g.get_repo(repo_name)
            commits = list(repo.get_commits())[:10]
            lines = [f"Letzte Commits in {repo_name}:"]
            for c in commits:
                msg = c.commit.message.split("\n")[0][:60]
                lines.append(f"  {c.sha[:7]} {msg} ({c.commit.author.name})")
            return "\n".join(lines)

        else:
            return f"Unbekannte GitHub-Aktion: {action}"

    except Exception as e:
        return f"GitHub Fehler: {e}"


# ── Main Entry Point ─────────────────────────────────────────────────────────

def hyper_connectivity_action(parameters: dict, player=None, speak=None) -> str:
    service = (parameters or {}).get("service", "").strip().lower()
    action = (parameters or {}).get("action", "").strip().lower()
    query = (parameters or {}).get("query", "")
    repo = (parameters or {}).get("repo", "")
    issue_title = (parameters or {}).get("issue_title", "")
    issue_body = (parameters or {}).get("issue_body", "")

    if player:
        player.write_log(f"[HyperConnect] service={service} action={action}")

    if service == "spotify":
        return spotify_action(action, query)

    elif service == "github":
        return github_action(action, repo, issue_title, issue_body)

    else:
        return (
            f"Unbekannter Dienst: {service}.\n\n"
            f"Verfügbar:\n"
            f"  service='spotify' – Aktionen: current, play, pause, next, previous, search, play_track, playlist, devices\n"
            f"  service='github'  – Aktionen: user, repos, issues, create_issue, prs, commits\n\n"
            f"Konfiguration in api_keys.json:\n"
            f"  spotify: spotify_client_id, spotify_client_secret\n"
            f"  github:  github_token"
        )
