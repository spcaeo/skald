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
 *
 * The visitor ID (to join the lead to the visit) is read by itself from the
 * skald_vid cookie or a form field named skald_vid, when your page has one.
 */

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
