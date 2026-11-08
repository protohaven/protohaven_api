<?php

/**
 * Lightweight CLI runner for the BookStack logical-theme unit tests.
 *
 * The *_test.php files are written for execution inside BookStack's Laravel
 * runtime. For pre-commit, we want to run them without booting all of
 * BookStack. The code under test only calls a handful of Laravel/BookStack
 * facades at the top level (Theme, Log, etc.), so this file defines minimal
 * stubs before loading functions.php. The actual test functions are then
 * discovered by their `test*` naming convention and called directly.
 */

namespace BookStack\Theming {
    class ThemeEvents
    {
        public const WEB_MIDDLEWARE_BEFORE = 'web_middleware_before';
        public const ROUTES_REGISTER_WEB = 'routes_register_web';
    }
}

namespace BookStack\Facades {
    class Theme
    {
        public static function listen($event, $callback): void
        {
            // Route/middleware registration is not needed by the unit tests.
        }
    }
}

namespace Illuminate\Routing {
    class Router
    {
    }
}

namespace Illuminate\Support\Facades {
    class Log
    {
        public static function info($message): void
        {
        }
    }

    class Session
    {
        public static function has($key)
        {
            return false;
        }

        public static function get($key)
        {
            return null;
        }

        public static function put($key, $value): void
        {
        }

        public static function forget($key): void
        {
        }
    }

    class Redirect
    {
        public static function to($url)
        {
            return new \ProtohavenTestResponse(302);
        }
    }
}

namespace {
    // oauth.php calls Log::info() without a `use` statement. In BookStack
    // Laravel registers a global `Log` class alias; provide the same here.
    class Log
    {
        public static function info($message): void
        {
        }
    }

    class ProtohavenTestResponse
    {
        private int $status;

        public function __construct(int $status)
        {
            $this->status = $status;
        }

        public function status(): int
        {
            return $this->status;
        }
    }

    function env($key, $default = null)
    {
        $value = getenv($key);
        return $value === false ? $default : $value;
    }

    function redirect($url)
    {
        return new ProtohavenTestResponse(302);
    }

    function response($content, $status = 200)
    {
        return new ProtohavenTestResponse($status);
    }

    // The theme's functions.php uses bare relative require_once paths that
    // assume the current working directory is the theme directory.
    chdir(__DIR__);
    require_once 'functions.php';

    $tests = array_values(array_filter(
        get_defined_functions()['user'],
        function ($name) {
            return strpos($name, 'test') === 0;
        }
    ));
    sort($tests, SORT_STRING);

    if (count($tests) === 0) {
        fwrite(STDERR, "No PHP unit tests found\n");
        exit(1);
    }

    $failures = [];
    foreach ($tests as $test) {
        try {
            $test();
            echo "PASS {$test}\n";
        } catch (Throwable $e) {
            $failures[] = [$test, $e->getMessage()];
            echo "FAIL {$test}: {$e->getMessage()}\n";
        }
    }

    if (count($failures) > 0) {
        fwrite(STDERR, count($failures) . " of " . count($tests) . " PHP tests failed\n");
        exit(1);
    }

    echo "ALL " . count($tests) . " PHP TESTS PASSED\n";
}
