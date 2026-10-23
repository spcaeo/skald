<?php
/**
 * Plugin Name: Skald Leads
 * Description: Tells Skald about each form sent on __SITE__ (Contact Form 7, WPForms, Gravity Forms, Elementor Pro forms, Ninja Forms). No code: activate it.
 * Version: 1.0.0
 * Requires at least: 5.0
 * Requires PHP: 7.0
 *
 * Each form sent becomes a lead in Skald, action "contact", with the email and
 * name fields it finds and the visitor's ID (the skald_vid cookie, or a hidden
 * field this plugin adds to your forms when the Skald script tag is on the page),
 * so Skald joins the lead to the visit. It posts to
 * __URL__
 * in the background (never slows or breaks a form), signed with the secret.
 *
 * __SECRET_NOTE__
 *
 * For developers: the filter 'skald_leads_action' ($action, $plugin, $fields)
 * changes the action; 'skald_leads_lead' ($lead, $plugin, $fields) changes the
 * whole lead, or drops it when it returns false.
 */

if (!defined('ABSPATH')) {
    exit;
}

function skald_leads_secret()
{
    if (defined('SKALD_LEAD_SECRET') && SKALD_LEAD_SECRET) {
        return (string) SKALD_LEAD_SECRET;
    }
    $env = getenv('SKALD_LEAD_SECRET');
    return $env ? $env : '__SECRET__';
}

/** The visitor ID: the hidden field (below), else the shared cookie. */
function skald_leads_vid()
{
    foreach (array('_POST', '_COOKIE') as $from) {
        $got = $from === '_POST' ? (isset($_POST['skald_vid']) ? $_POST['skald_vid'] : null)
                                 : (isset($_COOKIE['skald_vid']) ? $_COOKIE['skald_vid'] : null);
        if (is_string($got) && preg_match('/^skv_[A-Za-z0-9_-]{22}$/', $got)) {
            return $got;
        }
    }
    return null;
}

/** One text value: arrays (a checkbox, a name in parts) joined by spaces. */
function skald_leads_text($value)
{
    if (is_array($value)) {
        $value = implode(' ', array_filter(array_map('skald_leads_text', $value), 'strlen'));
    }
    return is_scalar($value) ? trim((string) $value) : '';
}

/** [email, name] from {"field key or label": value}, by their names. */
function skald_leads_find($fields)
{
    $email = '';
    $name = '';
    $first = '';
    $last = '';
    foreach ($fields as $key => $value) {
        $key = strtolower((string) $key);
        $value = skald_leads_text($value);
        if ($value === '') {
            continue;
        }
        if ($email === '' && strpos($key, 'mail') !== false && is_email($value)) {
            $email = $value;
        } elseif (strpos($key, 'mail') !== false) {
            continue;
        } elseif ($first === '' && preg_match('/first|given|fname/', $key)) {
            $first = $value;
        } elseif ($last === '' && preg_match('/last|family|surname|lname/', $key)) {
            $last = $value;
        } elseif ($name === '' && preg_match('/name/', $key) && !preg_match('/company|business|user/', $key)) {
            $name = $value;
        }
    }
    if ($email === '') {
        foreach ($fields as $value) {
            $value = skald_leads_text($value);
            if ($value !== '' && is_email($value)) {
                $email = $value;
                break;
            }
        }
    }
    if ($name === '') {
        $name = trim($first . ' ' . $last);
    }
    return array($email, substr($name, 0, 200));
}

/** Send one form entry to Skald, in the background. Never throws. */
function skald_leads_send($plugin, $entry_id, $fields)
{
    try {
        $secret = skald_leads_secret();
        if ($secret === '') {
            return;
        }
        $fields = is_array($fields) ? $fields : array();
        $id = $entry_id ? (string) $entry_id : strtolower(wp_generate_password(12, false));
        list($email, $name) = skald_leads_find($fields);
        $lead = array('external_ref' => $plugin . '-' . $id,
                      'action' => apply_filters('skald_leads_action', 'contact', $plugin, $fields));
        if ($email !== '') {
            $lead['email'] = $email;
        }
        if ($name !== '') {
            $lead['name'] = $name;
        }
        $vid = skald_leads_vid();
        if ($vid) {
            $lead['vid'] = $vid;
        }
        $lead = apply_filters('skald_leads_lead', $lead, $plugin, $fields);
        if (!is_array($lead)) {
            return;
        }
        $body = wp_json_encode($lead);
        $t = time();
        wp_remote_post('__URL__', array(
            'blocking' => false,
            'timeout' => 3,
            'data_format' => 'body',
            'body' => $body,
            'headers' => array(
                'Content-Type' => 'application/json',
                'User-Agent' => 'skald-leads-wordpress/1',
                'X-Skald-Signature' => 't=' . $t . ',v1=' . hash_hmac('sha256', $t . '.' . $body, $secret),
            ),
        ));
    } catch (\Throwable $e) {
        // A lead lost is better than a form broken.
    }
}

// Contact Form 7: after the mail is sent (no entry id: a random one).
add_action('wpcf7_mail_sent', function ($form) {
    try {
        $sub = class_exists('WPCF7_Submission') ? WPCF7_Submission::get_instance() : null;
        skald_leads_send('cf7', null, $sub ? $sub->get_posted_data() : array());
    } catch (\Throwable $e) {
    }
});

// WPForms: each field has a type, a label and a value.
add_action('wpforms_process_complete', function ($fields, $entry, $form_data, $entry_id = 0) {
    try {
        $flat = array();
        foreach ((array) $fields as $i => $field) {
            if (is_array($field)) {
                $key = (isset($field['type']) ? $field['type'] : '') . ' ' . (isset($field['name']) ? $field['name'] : $i);
                $flat[$key . ' #' . $i] = isset($field['value']) ? $field['value'] : '';
            }
        }
        skald_leads_send('wpforms', $entry_id, $flat);
    } catch (\Throwable $e) {
    }
}, 10, 4);

// Gravity Forms: the entry holds the values by field id.
add_action('gform_after_submission', function ($entry, $form) {
    try {
        $flat = array();
        foreach ((isset($form['fields']) ? $form['fields'] : array()) as $field) {
            $fid = is_object($field) ? $field->id : (isset($field['id']) ? $field['id'] : '');
            $type = is_object($field) ? $field->type : (isset($field['type']) ? $field['type'] : '');
            $label = is_object($field) ? $field->label : (isset($field['label']) ? $field['label'] : '');
            if (is_object($field) && method_exists($field, 'get_value_export')) {
                $value = $field->get_value_export($entry);
            } else {
                $value = isset($entry[(string) $fid]) ? $entry[(string) $fid] : '';
            }
            $flat[$type . ' ' . $label . ' #' . $fid] = $value;
        }
        skald_leads_send('gravity', isset($entry['id']) ? $entry['id'] : null, $flat);
    } catch (\Throwable $e) {
    }
}, 10, 2);

// Elementor Pro forms: the record's fields, each with a type, a title and a value.
add_action('elementor_pro/forms/new_record', function ($record, $handler) {
    try {
        $flat = array();
        foreach ((array) $record->get('fields') as $id => $field) {
            $flat[(isset($field['type']) ? $field['type'] : '') . ' ' . (isset($field['title']) ? $field['title'] : '') . ' ' . $id]
                = isset($field['value']) ? $field['value'] : '';
        }
        skald_leads_send('elementor', null, $flat);
    } catch (\Throwable $e) {
    }
}, 10, 2);

// Ninja Forms: the submission id when the form saves submissions.
add_action('ninja_forms_after_submission', function ($form_data) {
    try {
        $flat = array();
        foreach ((isset($form_data['fields']) ? (array) $form_data['fields'] : array()) as $i => $field) {
            $key = (isset($field['type']) ? $field['type'] : '') . ' ' . (isset($field['key']) ? $field['key'] : '') . ' '
                . (isset($field['label']) ? $field['label'] : '') . ' #' . $i;
            $flat[$key] = isset($field['value']) ? $field['value'] : '';
        }
        $sub = isset($form_data['actions']['save']['sub_id']) ? $form_data['actions']['save']['sub_id'] : null;
        skald_leads_send('ninja', $sub, $flat);
    } catch (\Throwable $e) {
    }
});

// The visitor ID for the forms: when the Skald script tag is on the page (with
// visitor IDs on), each form sent carries it in a hidden field named skald_vid.
add_action('wp_footer', function () {
    echo "<script>(function(){function v(){try{var i=typeof window.skald==='function'&&window.skald('id');"
        . "if(!i)i=localStorage.getItem('skald.vid');return /^skv_[\\w-]{22}$/.test(i||'')?i:''}catch(e){return ''}}"
        . "document.addEventListener('submit',function(e){var f=e.target,i=v(),h;if(!i||!f||f.tagName!=='FORM')return;"
        . "h=f.querySelector('input[name=skald_vid]');if(!h){h=document.createElement('input');h.type='hidden';"
        . "h.name='skald_vid';f.appendChild(h)}h.value=i},true)})();</script>\n";
}, 100);
