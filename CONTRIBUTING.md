# Contributing to Skald

Thank you for helping. Skald has one promise, *every visit, truly told*, and the rules below exist to
keep it. Please read them before you open a pull request.

## Set up in one minute

There is nothing to install. Skald uses the Python standard library only.

```sh
git clone https://github.com/spcaeo/skald && cd skald
python3 --version                      # 3.11 or newer
python3 -m unittest discover tests     # must end with OK
```

Node.js is optional. If `node` is on your path, a few tests also check the JavaScript (the `skald.js`
tag runs against a tiny fake DOM). To check every dashboard module parses:

```sh
for f in $(find skald beacon -name '*.js'); do cp "$f" /tmp/x.mjs && node --check /tmp/x.mjs || echo "FAIL $f"; done
```

The dashboard has no build step. Edit a file under `skald/webapp/`, reload the page.

## The house rules

1. **Every figure reconciles, or it is withheld.** Groups add up to the log exactly. A day that does
   not add up is withheld, never guessed, never drawn as zero.
2. **Every new figure is counted twice.** Add a second, independent count in an `audit*.py` file
   that shares only the name lists (bots, assistants) with the main code: its own parser or query,
   its own rules. No new figure ships without it.
3. **Never report requests as people.** Requests, people and machines are different units. "People"
   is an upper bound.
4. **Not recorded stays not recorded.** A figure that was not recorded is `null` (blank), never `0`.
5. **No personal data in history.** No address, no person's user agent, no name or email goes into
   stored history. If your change needs one, open an issue first.
6. **Standard library only.** No new runtime dependency. PyYAML stays optional.
7. **No file over 1,000 lines.** Split it before it crosses the line.
8. **No product, host or domain in the package.** Nothing in the `skald/` package names a real site.
   Examples use `example.com`.
9. **No secrets, anywhere.** No password, token, API key, SMTP login or real IP address in code,
   tests, docs or commit messages. Test data uses RFC 5737 addresses (`192.0.2.0/24`,
   `198.51.100.0/24`, `203.0.113.0/24`) and `example.com`.
10. **Off by default.** A new feature that changes what is collected or sent is off until the config
    turns it on, so existing installs work as before.

## Style

- Python: type hints where they help, small focused functions, docstrings that say *why*. Match
  the file you are in.
- JavaScript: plain ES modules, no framework, no third-party code, nothing fetched from another
  origin. The dashboard must keep working under its strict Content-Security-Policy.
- Words on screen and in docs: simple English, short sentences. Say what a number means and what it
  cannot know.
- Tests assert exact numbers against hand-built log fixtures in `tests/fixtures/`.

## Pull requests

1. Open an issue first for anything larger than a fix, so we can agree on the approach.
2. Branch from `main`. Keep one change per pull request.
3. Add or update tests. `python3 -m unittest discover tests` must end `OK`.
4. Update the docs the change touches, and add a line under "Unreleased" in
   [CHANGELOG.md](CHANGELOG.md).
5. Fill in the pull request template, including the audit question.

## Contributor licence agreement

Skald is released under the [Elastic License 2.0](LICENSE), and Space-O Technologies also offers it
under commercial licences (for example, for hosted use). To keep that possible, every contribution
needs this short agreement. You accept it by ticking the box in the pull request template.

> **Skald Contributor Licence Agreement (v1.0)**
>
> 1. "You" means the person or entity submitting a contribution. "Contribution" means any code,
>    documentation or other material you submit to this repository.
> 2. You keep the copyright in your contribution.
> 3. You grant Space-O Technologies and the recipients of software it distributes a perpetual,
>    worldwide, non-exclusive, royalty-free, irrevocable licence to use, copy, modify, distribute,
>    sublicense and relicense your contribution, including under the Elastic License 2.0 and under
>    commercial licences.
> 4. You grant the same parties a perpetual, worldwide, non-exclusive, royalty-free, irrevocable
>    patent licence for your contribution, as far as your patent claims are needed to use it.
> 5. You confirm that the contribution is your original work, or that you have the right to submit
>    it under these terms, and that, if your employer has rights in it, your employer has allowed
>    you to submit it.
> 6. You confirm that the contribution contains no secret, password, personal data or real IP
>    address.
> 7. The contribution is provided "as is", without warranty.

Each commit should also carry a sign-off line (`git commit -s`), which records that you accept the
agreement for that commit:

```
Signed-off-by: Your Name <you@example.com>
```

## Reporting security problems

Not in a public issue, please. See [SECURITY.md](SECURITY.md).

## Code of conduct

Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).
