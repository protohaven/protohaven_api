<?php

/**
 * Lightweight CLI runner for WordPress plugin unit tests.
 *
 * The plugins are written to run inside WordPress, so this file defines
 * minimal WordPress function stubs before loading each plugin and its
 * `*_test.php` file. Tests are plain functions named `test_*` and use the
 * assertion helpers defined here.
 */

define('ABSPATH', __DIR__ . '/');
ini_set('error_log', '/dev/null');

class WP_Error
{
    private string $message;

    public function __construct(string $message = '')
    {
        $this->message = $message;
    }

    public function get_error_message(): string
    {
        return $this->message;
    }

    public function __toString(): string
    {
        return $this->get_error_message();
    }
}

function reset_wp_test_state(): void
{
    $_GET = [];
    $GLOBALS['WP_REMOTE_GET_RESPONSES'] = [];
    $GLOBALS['WP_REMOTE_GET_REQUESTS'] = [];
    $GLOBALS['WP_OPTIONS'] = [];
    $GLOBALS['WP_CACHE'] = [];
}

function set_wp_remote_response($response): void
{
    $GLOBALS['WP_REMOTE_GET_RESPONSES'][] = $response;
}

function set_wp_option(string $name, $value): void
{
    $GLOBALS['WP_OPTIONS'][$name] = $value;
}

function set_wp_cache(string $key, $value): void
{
    $GLOBALS['WP_CACHE'][$key] = $value;
}

function wp_remote_requests(): array
{
    return $GLOBALS['WP_REMOTE_GET_REQUESTS'];
}

function assert_equal($a, $b, string $desc): void
{
    if ($a != $b) {
        $a = is_scalar($a) || $a === null ? var_export($a, true) : json_encode($a);
        $b = is_scalar($b) || $b === null ? var_export($b, true) : json_encode($b);
        throw new Exception("{$desc}: {$a} != {$b}");
    }
}

function assert_true($condition, string $desc): void
{
    if (!$condition) {
        throw new Exception($desc);
    }
}

/* WordPress API stubs used by the plugin code under test. */

function add_action($hook, $callback): void
{
}

function register_block_type($path): void
{
}

function register_rest_route($namespace, $route, $args): void
{
}

function add_options_page($page_title, $menu_title, $capability, $menu_slug, $callback, $position): void
{
}

function register_setting($option_group, $option_name): void
{
}

function add_settings_section($id, $title, $callback, $page): void
{
}

function add_settings_field($id, $title, $callback, $page, $section): void
{
}

function get_option($name)
{
    return $GLOBALS['WP_OPTIONS'][$name] ?? false;
}

function wp_remote_get($url, $args = [])
{
    $GLOBALS['WP_REMOTE_GET_REQUESTS'][] = ['url' => $url, 'args' => $args];
    if (count($GLOBALS['WP_REMOTE_GET_RESPONSES']) > 0) {
        return array_shift($GLOBALS['WP_REMOTE_GET_RESPONSES']);
    }
    return ['body' => '', 'response' => ['code' => 200]];
}

function wp_remote_retrieve_body($response)
{
    return $response['body'] ?? '';
}

function is_wp_error($thing): bool
{
    return $thing instanceof WP_Error;
}

function wp_cache_get($key)
{
    return $GLOBALS['WP_CACHE'][$key] ?? false;
}

function wp_cache_set($key, $value): void
{
    $GLOBALS['WP_CACHE'][$key] = $value;
}

function esc_attr($value)
{
    return htmlspecialchars((string) $value);
}

function settings_fields($group): void
{
}

function do_settings_sections($page): void
{
}

function submit_button(): void
{
}

chdir(__DIR__);

$plugin_files = glob('protohaven-*/protohaven-*.php');
$test_files = glob('protohaven-*/*_test.php');
sort($plugin_files, SORT_STRING);
sort($test_files, SORT_STRING);

foreach ($plugin_files as $file) {
    require_once $file;
}

foreach ($test_files as $file) {
    require_once $file;
}

$tests = array_values(array_filter(
    get_defined_functions()['user'],
    function ($name) {
        return strpos($name, 'test_') === 0;
    }
));
sort($tests, SORT_STRING);

if (count($tests) === 0) {
    fwrite(STDERR, "No WordPress PHP unit tests found\n");
    exit(1);
}

$failures = [];
foreach ($tests as $test) {
    try {
        reset_wp_test_state();
        $test();
        echo "PASS {$test}\n";
    } catch (Throwable $e) {
        $failures[] = [$test, $e->getMessage()];
        echo "FAIL {$test}: {$e->getMessage()}\n";
    }
}

if (count($failures) > 0) {
    fwrite(STDERR, count($failures) . ' of ' . count($tests) . ' WordPress PHP tests failed' . PHP_EOL);
    exit(1);
}

echo 'ALL ' . count($tests) . ' WORDPRESS PHP TESTS PASSED' . PHP_EOL;
