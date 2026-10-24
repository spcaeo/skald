# Send leads to Skald: one file, one line

These files tell Skald each time __SITE__ makes a lead (a contact form, a demo
request, a sign-up). Pick the one for your site, put it next to your code, and
call one function after the form is saved.

They post to `__URL__`.

## The one line

| Your site | File | The line |
| --- | --- | --- |
| PHP | `skald-lead.php` | `require_once __DIR__ . '/skald-lead.php';` then `skald_lead($id, 'contact', $email, $name);` |
| Node 18+ | `skald-lead.cjs` | `const { skaldLead } = require("./skald-lead.cjs");` then `await skaldLead(id, "contact", { email, name });` |
| Python 3.8+ | `skald_lead.py` | `from skald_lead import skald_lead` then `skald_lead(id, "contact", email=email, name=name)` |
| WordPress | `wordpress/skald-leads/` | No code: zip the `skald-leads` folder (or download `skald-leads.zip` from Skald), then **Plugins > Add New > Upload Plugin**, and **Activate** |

- `id` is your own id for the lead, such as the form entry's id. The same lead always sends the same id: a repeat is never counted twice.
- The second word is what was done: `contact`, `demo`, `signup`, `trial` (a short lowercase word).
- Email and name are optional. Skald keeps them only when the site's **Leads' names and emails** is **full**.
- Each function waits at most 3 seconds, never throws, and returns true when Skald kept the lead. When it returns false you can send the lead again later.
- Node from an ES module: `import { skaldLead } from "./skald-lead.cjs";` works too. The file ends in `.cjs` so it works in any Node project, and so email services do not block it.
- Other fields go in the last argument: `label` (`sales`, `support`), `stage` (`won`, `lost`...), `test: true` for your own team's tests, `vid`. PHP: `skald_lead($id, 'demo', $email, $name, ['label' => 'sales']);`. Python: `skald_lead(id, "demo", label="sales")`.
- Money: `value` (the amount in the currency's units, like `49.99`), `currency` (`USD`), `customer_ref` (your own customer id, never an email, a phone number or an IP address: such a reference is dropped, with a note) and `tags` (up to 5, like `{"plan": "pro"}`). Python: `skald_lead(order_id, "signup", stage="paid", value=49.99, currency="USD", customer_ref=customer_id)`. A renewal is a new `paid` with the invoice's own id and the same `customer_ref`. A refund is `stage="refunded"` on the sale's id, with `value` the total refunded so far (no value: all of it), in the sale's currency and never more than the sale. A later, larger total counts the difference on the day it arrives. Skald never converts currencies.
- WordPress: money comes only from your own code on the server, never from the form: any visitor can type any amount into a form. Add it in the `skald_leads_lead` filter, from your own records: `add_filter('skald_leads_lead', function ($lead, $plugin, $fields) { $lead['value'] = '49.00'; $lead['currency'] = 'USD'; return $lead; }, 10, 3);`

The WordPress plugin works with Contact Form 7, WPForms, Gravity Forms, Elementor Pro forms and Ninja Forms. Each form sent becomes a lead with the action `contact`, the email and name fields it finds, and an id like `wpforms-123`.

## Where the secret lives

The files sign each lead with your lead hook's secret, so nobody else can send fake leads.

- Best: an environment variable on your server named `SKALD_LEAD_SECRET`. Every file reads it first.
- WordPress: add this line to `wp-config.php`, above "That's all, stop editing!": `define('SKALD_LEAD_SECRET', 'your-secret');`
- If you downloaded a file with the secret written in it, it works as it is. Still, move the secret to the environment variable (or `wp-config.php`) when you can, and never put the file in a public place or a public code repository.
- Never put the secret in a web page or in the browser's JavaScript.

Lost the secret? Make a new one in Skald (**Settings > Integrations > Your site's server (lead) > Rotate secret**). The old one stops working at once.

## Join the lead to the visit

Skald can show the pages a lead read before the form, when the lead carries the visitor's ID.

1. Put Skald's script tag on your pages (Skald: **Settings > Integrations**, copy the tag), and ask your Skald admin to turn visitor IDs on for the site:

   ```
   <script src="__ORIGIN__/traffic-js/skald.js" data-site="__SITE__" defer></script>
   ```

2. Send the ID with the lead. The page knows it as `skald('id')`. Two easy ways to bring it to your server:
   - **A hidden field.** Add `<input type="hidden" name="skald_vid">` to the form, and fill it before the form is sent: `form.skald_vid.value = skald('id') || ''`.
   - **The cookie.** With "Share across subdomains" on (on the tag: `data-share-subdomains="true"`, or in Skald's settings), the ID is also in a first-party cookie named `skald_vid`.

The PHP file and the WordPress plugin read the field or the cookie by themselves. In Node and Python, pass it: `vid: req.body.skald_vid || req.cookies.skald_vid` or `vid=request.form.get("skald_vid")`.

## No code: Zapier and form tools

A tool that cannot sign (Zapier's **Webhooks by Zapier**, a form plugin's webhook with custom headers) can send the secret as a plain key instead:

- **Method:** POST
- **URL:** `__URL__`
- **Header:** `Authorization: Bearer <your secret>`
- **Header:** `Content-Type: application/json`
- **Body:**

  ```
  {"external_ref": "form-123", "action": "contact", "email": "person@example.com", "name": "A Person"}
  ```

In Zapier: **Webhooks by Zapier > POST**, Payload Type `json`, the fields `external_ref` and `action` (map the entry's id to `external_ref`), and the header above. Keep the secret only in the tool's own settings, and use the address exactly as above (it starts with `https://`): the key travels with each message.

## Check it

Send one form, then open Skald: **Settings > Integrations > Your site's server (lead)**. **Last deliveries** shows it as "kept", or says why it was refused ("bad signature": the secret does not match).
