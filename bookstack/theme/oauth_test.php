<?php
use BookStack\Theming\ThemeEvents;
use BookStack\Facades\Theme;
use Illuminate\Routing\Router;
use Illuminate\Support\Facades\Log;
use PHPUnit\Framework\TestCase;

require_once("oauth.php");

function testOauthRedirectUri() {
  assert_equal(oauthRedirectUri("test_client", "test_redir"), "https://protohaven.app.neoncrm.com/np/oauth/auth?response_type=code&client_id=test_client&redirect_uri=test_redir", "Simple test of redirect URI");
}

function testExtractNeonRoles() {
    $accInfo = [
        'individualAccount' => [
            'accountCustomFields' => [
                [
                    'name' => 'API server role',
                    'optionValues' => [
                        ['name' => 'Admin'],
                        ['name' => 'Editor'],
                        ['name' => 'Viewer']
                    ]
                ]
            ]
        ]
    ];
    $expected = ['Admin', 'Editor', 'Viewer'];

    assert_equal($expected, extractNeonRoles($accInfo), "extractNeonRoles full");
}

function testExtractNeonRolesNoCustomFields() {
    $accInfo = [
        'individualAccount' => [
            'accountCustomFields' => []
        ]
    ];

    assert_equal(extractNeonRoles($accInfo), null, "extractNeonRoles empty");
}

function testComputeRoleChanges() {
  $got = computeRoleChanges(
    ["Shop Tech"],
    ["Admin", "Public", "Member"],
    array_map(function($s) { return (object) ['id' => $s, 'display_name' => $s]; }, ["Admin", "Public", "Member", "Shop Tech"]),
  );
  assert_equal($got['detach'], ['Member'], "Member role is removed; Public & Admin roles unchanged");
  assert_equal($got['attach'], ['Shop Tech'], "Shop tech role added");
}

function testComputeRoleChangesNullEntries() {
  $got = computeRoleChanges(null, null, []);
  assert_equal($got['detach'], [], "no detach");
  assert_equal($got['attach'], [], "no attach");
}

function testOauthMiddlewareHook() {
  $result = oauthMiddlewareHook("testurl", null, null, null, null, null, null);
  assert_equal($result->status(), 302, "Redirects when no auth code on login page");

  $result = oauthMiddlewareHook("testurl", "testcode", function($code) { return null; }, null, null, null, null);
  assert_equal($result->status(), 500, "Errors when code invalid");

  $getTokenOk = function($code) { return "testtoken"; };
  $result = oauthMiddlewareHook("testurl", "testcode", $getTokenOk, function($token) { return null; }, null, null, null);
  assert_equal($result->status(), 500, "Handles metadata fetch error");

  $accInfoFn = function($token) { return ["email" => "foo@bar.com", "firstName" => "first", "lastName" => "last", "roles" => []]; };
  $upsertUserFn = function($email, $firstName, $lastName) {
    assert_equal($email, "foo@bar.com", "user email");
    assert_equal($firstName, "first", "user firstname");
    assert_equal($lastName, "last", "user lastname");
    return (object) ['id' => 'testuser'];
  };
  $syncRolesCalled = false;
  $syncRolesFn = function($roles, $user) use (&$syncRolesCalled) {
      $syncRolesCalled = true;
  };
  $loggedIn = false;
  $loginFn = function($user) use (&$loggedIn) { $loggedIn = true; };

  oauthMiddlewareHook("testurl", "testcode", $getTokenOk, $accInfoFn, $upsertUserFn, $syncRolesFn, $loginFn);
  assert_equal($syncRolesCalled, true, "roles synced");
  assert_equal($loggedIn, true, "logged in");
}


Theme::listen(ThemeEvents::ROUTES_REGISTER_WEB, function (Router $router) {
  $router->get('/unittest/oauth', function () {
    testOauthRedirectUri();
    testExtractNeonRoles();
    testExtractNeonRolesNoCustomFields();
    testComputeRoleChanges();
    testComputeRoleChangesNullEntries();
    testOauthMiddlewareHook();
    echo "ALL TESTS PASS";
  });
});
?>
