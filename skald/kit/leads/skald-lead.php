<?php
/**
 * Skald lead helper for __SITE__: one file, one function.
 *
 *   require_once __DIR__ . '/skald-lead.php';
 *   skald_lead($entry_id, 'contact', $email, $name);
 *
 * It tells Skald a lead was made: a signed POST to
 * __URL__
 * Call it after your form is saved. It waits at most 3 seconds, never throws,
 * and returns true when Skald kept the lead (false otherwise: you can send
 * it again later, a repeat is never counted twice).
 *
 * __SECRET_NOTE__
 *
 * $ref     your own id for the lead (the same lead always sends the same id)
 * $action  a short lowercase word: 'contact', 'demo', 'signup', 'trial'
 * $extra   other fields, such as ['label' => 'sales', 'stage' => 'won',
 *          'vid' => '...', 'test' => true]. See README.md.
 *          Money (Skald 2.32): ['value' => 49.99, 'currency' => 'USD',
 *          'customer_ref' => 'your-customer-id', 'tags' => ['plan' => 'pro']]
 *          (the amount in the currency's units; never an email as
 *          customer_ref). A refund: 'stage' => 'refunded' on the sale's ref,
 *          'value' = the total refunded so far (no value: all of it).
 *
 * The visitor ID (to join the lead to the visit) is read by itself from the
 * skald_vid cookie or a form field named skald_vid, when your page has one.
 *
 * The visitor's address (so Skald records the lead's country; it looks the
 * country up and drops the address at once) is read by itself too, from the
 * request that made the lead: REMOTE_ADDR. When that is a private or local
 * address (a proxy on your own server), the X-Real-IP header, else the first
 * X-Forwarded-For entry. Behind a host or CDN that sets its own header, name
 * it in the environment variable SKALD_LEAD_IP_HEADER (or define() it):
 * Cloudflare 'CF-Connecting-IP', Vercel 'X-Forwarded-For', a load balancer
 * 'X-Forwarded-For'. See README.md, "The visitor's address". Pass
 * 'ip' => $address in $extra to choose it yourself ('ip' => null sends none):
 * a lead sent later from a queue or a cron job has no request, so keep the
 * address with the job and pass it.
 */

if (!function_exists('skald_lead_ip_of')) {
    /** An IPv4 or IPv6 address from a value: the first of a list, without a port; else null. */
    function skald_lead_ip_of($value)
    {
        if (!is_scalar($value)) {
            return null;
        }
        $parts = explode(',', (string) $value);
        $got = trim($parts[0]);
        if (preg_match('/^(\d{1,3}(?:\.\d{1,3}){3}):\d{1,5}$/', $got, $m)
            || preg_match('/^\[([0-9A-Fa-f:.]+)\](?::\d{1,5})?$/', $got, $m)) {
            $got = $m[1];
        }
        return filter_var($got, FILTER_VALIDATE_IP) !== false ? $got : null;
    }
}

if (!function_exists('skald_lead_visitor_ip')) {
    /** The visitor's address in this request (see the top of this file), or null. */
    function skald_lead_visitor_ip()
    {
        $name = getenv('SKALD_LEAD_IP_HEADER');
        if (!$name && defined('SKALD_LEAD_IP_HEADER')) {
            $name = (string) constant('SKALD_LEAD_IP_HEADER');
        }
        if ($name && strtoupper($name) !== 'REMOTE_ADDR') {
            $key = 'HTTP_' . strtoupper(str_replace('-', '_', $name));
            return isset($_SERVER[$key]) ? skald_lead_ip_of($_SERVER[$key]) : null;
        }
        $remote = isset($_SERVER['REMOTE_ADDR']) ? skald_lead_ip_of($_SERVER['REMOTE_ADDR']) : null;
        if ($name || $remote === null
            || filter_var($remote, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE) !== false) {
            return $remote;
        }
        foreach (array('HTTP_X_REAL_IP', 'HTTP_X_FORWARDED_FOR') as $key) {
            $got = isset($_SERVER[$key]) ? skald_lead_ip_of($_SERVER[$key]) : null;
            if ($got !== null) {
                return $got;
            }
        }
        return $remote;
    }
}

if (!function_exists('skald_lead')) {
    function skald_lead($ref, $action, $email = null, $name = null, $extra = array())
    {
        try {
            $secret = getenv('SKALD_LEAD_SECRET');
            if (!$secret) {
                $secret = '__SECRET__';
            }
            if ($secret === '' || (string) $ref === '' || (string) $action === '') {
                return false;
            }
            $lead = is_array($extra) ? $extra : array();
            if (isset($lead['tags']) && is_array($lead['tags']) && !$lead['tags']) {
                unset($lead['tags']);       // an empty PHP array is a JSON list, not tags
            }
            $lead['external_ref'] = (string) $ref;
            $lead['action'] = (string) $action;
            if ($email !== null && $email !== '') {
                $lead['email'] = (string) $email;
            }
            if ($name !== null && $name !== '') {
                $lead['name'] = (string) $name;
            }
            if (!isset($lead['vid'])) {
                foreach (array(isset($_POST['skald_vid']) ? $_POST['skald_vid'] : null,
                               isset($_COOKIE['skald_vid']) ? $_COOKIE['skald_vid'] : null) as $vid) {
                    if (is_string($vid) && preg_match('/^skv_[A-Za-z0-9_-]{22}$/', $vid)) {
                        $lead['vid'] = $vid;
                        break;
                    }
                }
            }
            $ip = array_key_exists('ip', $lead) ? skald_lead_ip_of($lead['ip']) : skald_lead_visitor_ip();
            if ($ip !== null) {
                $lead['ip'] = $ip;
            } else {
                unset($lead['ip']);
            }
            $body = json_encode($lead);
            if ($body === false) {
                return false;
            }
            $t = time();
            $headers = array(
                'Content-Type: application/json',
                'User-Agent: skald-lead-php/1',
                'X-Skald-Signature: t=' . $t . ',v1=' . hash_hmac('sha256', $t . '.' . $body, $secret),
            );
            $url = '__URL__';
            if (function_exists('curl_init')) {
                $ch = curl_init($url);
                curl_setopt_array($ch, array(
                    CURLOPT_POST => true, CURLOPT_POSTFIELDS => $body, CURLOPT_HTTPHEADER => $headers,
                    CURLOPT_RETURNTRANSFER => true, CURLOPT_CONNECTTIMEOUT => 2, CURLOPT_TIMEOUT => 3,
                ));
                curl_exec($ch);
                $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
                if (PHP_VERSION_ID < 80000) {
                    curl_close($ch);
                }
                return $code >= 200 && $code < 300;
            }
            $context = stream_context_create(array('http' => array(
                'method' => 'POST', 'header' => implode("\r\n", $headers), 'content' => $body,
                'timeout' => 3, 'ignore_errors' => true,
            )));
            $stream = @fopen($url, 'r', false, $context);
            if ($stream === false) {
                return false;
            }
            $meta = stream_get_meta_data($stream);
            fclose($stream);
            $status = isset($meta['wrapper_data'][0]) ? (string) $meta['wrapper_data'][0] : '';
            return (bool) preg_match('#^HTTP/\S+\s+2\d\d#', $status);
        } catch (\Throwable $e) {
            return false;
        }
    }
}
