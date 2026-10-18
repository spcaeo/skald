## What and why

<!-- What does this change, and why? Link the issue: "Fixes #123". -->

## How it was tested

<!-- Tests added or changed. Paste the last line of `python3 -m unittest discover tests`. -->

## Checklist

- [ ] `python3 -m unittest discover tests` ends `OK`.
- [ ] **New figure?** It has a second, independent count in an `audit*.py` file that shares only
      the name lists with the main code. (Or: this change adds no figure.)
- [ ] Figures still reconcile; nothing unrecorded is shown as `0`; requests are never called people.
- [ ] No address, person's user agent, name or email goes into stored history.
- [ ] Standard library only; no new runtime dependency.
- [ ] No file is over 1,000 lines.
- [ ] No secrets, real IP addresses or real domains (tests use RFC 5737 addresses and `example.com`).
- [ ] Anything that changes what is collected or sent is off by default.
- [ ] Docs and `CHANGELOG.md` ("Unreleased") are updated.

## Contributor licence agreement

- [ ] I have read the Contributor Licence Agreement in [CONTRIBUTING.md](https://github.com/spcaeo/skald/blob/main/CONTRIBUTING.md) and I
      agree to it for this contribution. My commits are signed off (`git commit -s`).
