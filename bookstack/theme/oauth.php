<?php
use BookStack\Access\LoginService;
use BookStack\Theming\ThemeEvents;
use BookStack\Facades\Theme;
use Illuminate\Routing\Router;
use BookStack\Users\Models\User;
use BookStack\Users\Models\Role;
use Illuminate\Http\Request;
use Illuminate\Support\Str;
use Illuminate\Support\Facades\Session;
# use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Redirect;

function oauthRedirectURI($client_id, $redirect_uri) {
    return "https://protohaven.app.neoncrm.com/np/oauth/auth?response_type=code&client_id={$client_id}&redirect_uri={$redirect_uri}";
}

function fetchAccessToken($clientId, $clientSecret, $redirectUri, $authorizationCode) {
  return Http::asForm()->post('https://app.neoncrm.com/np/oauth/token', [
    'client_id' => $clientId,
    'client_secret' => $clientSecret,
    'redirect_uri' => $redirectUri,
    'code' => $authorizationCode,
    'grant_type' => 'authorization_code',
  ])->throw()->json()['access_token'];
}

function extractNeonRoles($accInfo) {
  if (isset($accInfo['individualAccount']['accountCustomFields'])) {
    foreach ($accInfo['individualAccount']['accountCustomFields'] as $field) {
      if (isset($field['name']) && $field['name'] === 'API server role') {
        return array_map(function($entry) {
          return $entry['name'];
        }, $field['optionValues']);
      }
    }
  }
}

// See https://developer.neoncrm.com/authenticating-constituents/
function getAccountInfo($user, $password, $accessToken) {
  $accInfo = Http::get("https://{$user}:{$password}@api.neoncrm.com/v2/accounts/{$accessToken}")->throw()->json();
  if (!$accInfo) {
    return null;
  }
  $data = [
    'email' => $accInfo['individualAccount']['primaryContact']['email1'],
    'firstName' => $accInfo['individualAccount']['primaryContact']['firstName'],
    'lastName' => $accInfo['individualAccount']['primaryContact']['lastName'],
    'roles' => extractNeonRoles($accInfo),
  ];
  if ($accInfo['individualAccount']['accountCurrentMembershipStatus'] == 'Active') {
	  $data['roles'][] = "Member";
  }
  return $data;
}

function computeRoleChanges($neon_roles, $cur_roles, $all_roles) {
  // Given string arrays $neon_roles and $cur_roles, loop through $all_roles and compute the
  // mutation needed to sync a user to only have $neon_roles.
  $ROLES_GRANTING_APPROVER = ["Shop Tech Lead", "Education Lead", "Maintenance Crew", "Board Member", "Staff"];
  $APPROVER_ROLE = "Wiki Approver";
  Log::info("User has Neon roles" . json_encode($neon_roles) . " and Bookstack roles " . json_encode($cur_roles));
  if (is_null($cur_roles)) {
	  $cur_roles = [];
  }
  if ( is_null($neon_roles)) {
      $neon_roles = [];
  }
  $result = ["attach" => [], "detach" => []];
  foreach ($all_roles as $role) {
    $name = $role->display_name;
    Log::info($name);
    if ($name == "Admin" || $name == "Public") {
      continue; // We don't mess with admin & public roles
    }

    if ($name == $APPROVER_ROLE) {
      // Approver role is a union of "leadership" roles and handled specially.
      // Note that Approver role is NOT auto-revoked. This is intentional, as
      // otherwise a Tech Lead that leaves the program would get their Approver
      // role revoked and thus invalidate all of their prior approvals.
      foreach ($ROLES_GRANTING_APPROVER as $name2) {
        if (in_array($name2, $neon_roles) && !in_array($APPROVER_ROLE, $cur_roles)) {
          Log::info("Add approver");
          array_push($result["attach"], $role->id);
        }
      }
      continue;
    }

    if (in_array($name, $neon_roles) && !in_array($name, $cur_roles)) {
      Log::info("Add role " . $name);
      array_push($result["attach"], $role->id);
    } else if (!in_array($name, $neon_roles) && in_array($name, $cur_roles)) {
      Log::info("Remove role " . $name);
      array_push($result["detach"], $role->id);
    }
  }
  return $result;
}

function syncNeonRoles($neon_roles, $user) {
  $all_roles = Role::all();
  $cur_role_names = array_map(function($role) {
      return $role['display_name'];
  }, $user->roles->toArray());

  Log::info("User has Neon roles" . json_encode($neon_roles) . " and Bookstack roles " . json_encode($cur_role_names));

  $changes = computeRoleChanges($neon_roles, $cur_role_names, $all_roles);
  foreach ($changes['attach'] as $a) {
    $user->roles()->attach($a);
  }
  foreach ($changes['detach'] as $d) {
    $user->roles()->detach($d);
  }
  if (!empty($changes['attach']) || !empty($changes['detach'])) {
    $user->unsetRelation('roles');
    $user->save();
  }
}

function upsertUserByEmail($email, $firstName, $lastName) {
  $user = User::query()->where('email', '=', $email)->first();
  if (!$user) {
      Log::info("User with email {$email} not found; inserting new User");
      $user = new User;
      $user->name = "{$firstName} {$lastName}";
      $user->email = $email;
      $user->password = Str::random(32);
      $user->refreshSlug();
      $user->save();
      $user->attachDefaultRole(); # Requires record to be created and have ID
      $user->save();
  }
  return $user;
}

function loginAsUser($user) {
  Log::info("Protohaven: login user {$user->id}");
  $loginService = app()->make(LoginService::class);
  $loginService->login($user, 'protohaven_oauth');
}

// Modified version of
// https://github.com/BookStackApp/BookStack/pull/2289#issuecomment-857164663
function oauthMiddlewareHook($url, $authCode, $fetchAccessToken, $getAccountInfo, $upsertUserByEmail, $syncNeonRoles, $loginAsUser) {
  $CLIENT_ID = env("NEON_CLIENT_ID");
  $CLIENT_SECRET = env("NEON_CLIENT_SECRET");
  $USER = env("NEON_USER");
  $PASS = env("NEON_PASS");
  $contact = env("ERR_CONTACT", "membership@protohaven.org");

  if (!$authCode) {
    return redirect(oauthRedirectURI($CLIENT_ID, $url));
  }

  $accessToken = $fetchAccessToken($CLIENT_ID, $CLIENT_SECRET, $url, $authCode);
  if (!$accessToken) {
    return response("500 Internal Server Error handling OAuth token. Please try again later or contact $contact.", 500);
  }

  // OAuth by default just returns token information. We make a secondary
  // request to get account metadata so that the user can be referenced by
  // ID and potentially created using existing account info.
  $acc= $getAccountInfo($USER, $PASS, $accessToken);
  if (!$acc) {
    return response("500 Internal Server Error fetching account details. Please try again later or contact $contact.", 500);
  }

  $user = $upsertUserByEmail($acc['email'], $acc['firstName'], $acc['lastName']);
  $syncNeonRoles($acc['roles'], $user);
  $loginAsUser($user);

  if (Session::has('post_login_redirect')) {
      $redirectUrl = Session::get('post_login_redirect');
      Session::forget('post_login_redirect');
      return Redirect::to($redirectUrl);
  }
  return Redirect::to('/');
}

function isAPIKeyValid($request) {
  $env_key = getenv('PH_BOOKSTACK_API_KEY');
  $hdr_key = $request->header('X-Protohaven-Bookstack-API-Key');
  if (!$env_key || $env_key != $hdr_key) {
    return false;
  }
  return true;
}

Theme::listen(ThemeEvents::WEB_MIDDLEWARE_BEFORE, function(Request $request) {
  $hasAuth = auth()->check() || isAPIKeyValid($request);
  $isLoginPage = $request->path() == "login";
  if (!$isLoginPage && !$hasAuth) {
    // We need to know where the user comes from so they can be redirected back
    // after OAuth
    $redirect = request()->url();
    $requestUrl = url('/');
    Log::info("$redirect vs $requestUrl");
    if (strpos($redirect, $requestUrl) !== 0) {
        $redirect = $requestUrl;
    }
    Session::put('post_login_redirect', $redirect);
    Log::info("Stored post login redirect: ". $redirect);
  }

  // We only want to do OAuth when not authenticated and on the login page
  if (!$isLoginPage || $hasAuth) {
    return;
  }


  // Inject methods to support unit tests - see test.php
  return oauthMiddlewareHook(
    $request->url(),
    $request->input('code', null),
    "fetchAccessToken",
    "getAccountInfo",
    "upsertUserByEmail",
    "syncNeonRoles",
    "loginAsUser",
  );
});

?>
