<?php
use BookStack\Entities\Queries\PageQueries;
use BookStack\Entities\Models\Page;
use BookStack\Theming\ThemeEvents;
use BookStack\Facades\Theme;
use Illuminate\Routing\Router;
use BookStack\Users\Models\Role;
use Illuminate\Support\Facades\Log;

$approvers = array();
function getApproverIDs() {
  global $approvers;
  $approvers = array();
  // This could be cached in the future
  $roles = Role::whereIn('display_name', array('Shop Tech Lead', 'Admin', 'Education Lead', 'Staff', 'Board Member'))->get()->all();
  foreach ($roles as $r) {
    foreach ($r->users()->get()->all() as $u) {
      $approvers[$u->id] = true;
    }
  }
  return $approvers;
}

class Approval {
  const DEFAULT_APPROVAL_THRESH = 2;

  public static function getPageState(Page $page, int $rev_id, int $thresh) {
    $cc = $page->comments()->with('createdBy')->get()->all();
    $approvers = getApproverIDs();
    $cc = array_map(function($c) { return ["html" => $c->html, "author" => $c['updated_by']]; }, $cc);

    $result = Approval::resolveState($cc, $approvers, $thresh);
    if (!$rev_id) {
      $cur_rev = $page->currentRevision()->get()->first();
    } else {
      $cur_rev = $page->revisions()->where('id', $rev_id)->get()->first();
    }
    if (!is_null($cur_rev)) {
      $result["current_revision"] = $cur_rev->revision_number;
      $result['current_id'] = $cur_rev->id;
    }
    $result["thresh"] = $thresh;

    # A page "#1" revision could actually be .../revisions/4 in the URL, as it's by ID
    # and not rev number. We must resolve the revision ID here so that we can provide
    # a link to the user.
    $approved = $page->revisions()->where('revision_number', $result['approved_revision'])->get()->first();
    if ($approved) {
        $result['approved_id'] = $approved->id;
    }
    return $result;
  }

  public static function extractCommand($comment) {
    if (preg_match('/(approve|reject)\s*#forever/i', $comment, $matches)) {
      return ["action" => strtolower($matches[1]), "rev" => "all"];
    }

    if (!preg_match('/(approve|reject)\s*#(\d+)/i', $comment, $matches)) {
      return null;
    }
    $a = strtolower($matches[1]);
    $r = (int)$matches[2];
    return ["action" => $a, "rev" => $r];
  }

  public static function resolveState($cc, $approvers, $thresh) {
    $latest_approved = null;
    $revs_approval = array();
    foreach ($cc as $c) {
      if (!array_key_exists($c['author'], $approvers)) {
        continue;
      }
      $m = Approval::extractCommand($c['html'], $approvers);
      if (!$m) {
        continue;
      }
      if ($m['action'] == "approve" && $m['rev'] == "all") {
        $latest_approved = "all";
        break;
      } else if ($m['action'] == "reject") {
        $revs_approval[$m['rev']] = [];
      } else { // action == approve
        if (!array_key_exists($m['rev'], $revs_approval)) {
          $revs_approval[$m['rev']] = array();
        }
        if (!in_array($c['author'], $revs_approval[$m['rev']])) {
          array_push($revs_approval[$m['rev']], $c['author']);
        }
        if (count($revs_approval[$m['rev']]) >= $thresh && (is_null($latest_approved) || $m['rev'] > $latest_approved)) {
          $latest_approved = $m['rev'];
        }
      }
    }
    return array(
      "approved_revision" => $latest_approved,
      "approvals" => $revs_approval,
    );
  }
}

function requiresApproval($book_slug, $page_slug) {
  $APPROVAL_RE = getenv("PAGE_APPROVAL_REGEXP", "/tools\\/*/");
  return preg_match($APPROVAL_RE, "$book_slug/$page_slug", $matches);
}

Theme::listen(ThemeEvents::ROUTES_REGISTER_WEB, function (Router $router) {
  Log::info("Prefetching approver IDs");
  getApproverIDs();
  Log::info("Registering Protohaven custom routes");

  $router->get('/approvals/{book_slug}/{page_slug}/{rev_id}', function ($book_slug, $page_slug, $rev_id) {
    if (requiresApproval($book_slug, $page_slug)) {
      $pq = new PageQueries();
      $page = $pq->findVisibleBySlugsOrFail($book_slug, $page_slug);
      Log::info($page->id);
      echo json_encode(Approval::getPageState($page, (int)$rev_id));
    } else {
      echo json_encode(["ignore" => true]);
    }
  });

  $router->get('/approvals', function () {
    ?>
    <h2>Page approvals process:</h2>
    <p>The following pages need approvals and will display a disclaimer on the page until they're approved.</p>
    <p>Approvals may be given by Tech Leads, Admins, Board Members, Staff, and Education Leads.</p>
    <p>To approve e.g. revision 3 of a page as one of these roles, comment "Approve #3" in the comments section at the bottom of the page.</p>
    <p>Approvers can also comment "Reject #3" to reset the approval counter of the given page.</p>
    <p>To exclude a page from the approval process, comment "Approve #forever".</p>
    <p>Only books/pages matching $PAGE_APPROVAL_REGEXP in the Booked server's env will be enrolled in the approvals process.</p>
    <p>See <a href="https://github.com/protohaven/server_config/" target="_blank">https://github.com/protohaven/server_config/</a> for implementation details.</p>
    <hr/>
    <h2>Pages requiring approval:</h2>
    <?php
    foreach (Page::select('*')->get()->all() as $page) {
      Log::info($page->id);
      $book = $page->book()->get()->first();
      if (!$page->slug) {
	continue; // Book headers are considered pages, but have no slug.
      }
      if (!requiresApproval($book->slug, $page->slug)) {
        continue;
      }

      $state = Approval::getPageState($page, 0, null);
      $cr = $state['current_revision'];
      $ar = $state['approved_revision'];
      if ($cr == $ar || $ar == "all") {
        continue;
      }
      $url = "/books/" . $book->slug . "/page/" . $page->slug;
      echo "<div>";
      echo "<p><strong><a href=\"$url\" target=\"blank\">$page->name (#$page->id) rev $cr</a></strong></p>";
      echo "<p>Approvals needed: ";
      if (!array_key_exists($cr, $state['approvals'])) {
        echo $state['thresh'];
      } else {
        echo $state['thresh'] - count($state['approvals'][$cr]);
      }
      echo "</p>";
      if (!is_null($ar)) {
        echo "<p>Last approved: <a href=\"$url/revisions/$ar\" target=\"blank\">rev $ar</a></p>";
      }
      echo "</div>";
    }
  });
});

?>
