## Step __N__. Check the privacy settings

Skald can keep each visit with the visitor's IP address, so the user can look a person up
later. The site's privacy notice should say so.

**Check first.** Skald's setting for this site now: __PRIVACY_NOW__. If the user chose it
already and the notice covers it, this job is done already.

1. Find the site's privacy notice: the footer's link, a page such as `/privacy` or
   `/privacy-policy`, or the page's file in the code. Read it.
2. Note what it says about server logs, IP addresses, how long they are kept, and why.
3. Ask the user, in one message, and wait for the answer:

   "Skald can keep each visit with the visitor's IP address, so you can look a person up
   later. Your privacy notice <says this / does not mention it>. Should Skald keep visitors'
   IP addresses? If yes, for how many days?"

4. Recommend what fits the notice: keep IP addresses only when the notice covers it, and no
   longer than it says. If the notice does not cover it, offer the user a short paragraph to
   add, and change their notice only with their yes, like any other change to the site.

Change nothing in Skald. Put the answer in the report as `privacy` (`keep_ips`, `days`,
`notice_url`): the user applies it in Skald with one click.
