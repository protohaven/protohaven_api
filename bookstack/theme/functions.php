<?php

/* Custom code for OAuth authentication of Protohaven users into Bookstack
 * Scott Martin, smartin015@gmail.com
 * Oct 9, 2024
 *
 * This uses Bookstack's "Logical Themes" feature to inject middleware into
 * the /login URL. This is necessary to use Neon CRM as an OAuth2 provider,
 * which is the case for e.g. our Booked reservation system.
 *
 * This design closely follows the guide provided by Neon CRM at
 * https://developer.neoncrm.com/authenticating-constituents/
 *
 * Read more about logical themes at
 * https://github.com/BookStackApp/BookStack/blob/development/dev/docs/logical-theme-system.md
 */

function assert_equal($a, $b, $desc) {
  if ($a != $b) {
    throw new AssertionError("$desc: $a != $b");
  }
}

require_once("oauth.php");
require_once("oauth_test.php");
require_once("approvals.php");
require_once("approvals_test.php");
require_once("backups.php");
require_once("tool_maintenance_history.php");
require_once("tool_links.php");
?>
