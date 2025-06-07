<?php
use BookStack\Entities\Queries\PageQueries;
use BookStack\Entities\Models\Page;
use BookStack\Theming\ThemeEvents;
use BookStack\Facades\Theme;
use Illuminate\Routing\Router;
use BookStack\Users\Models\Role;
use Illuminate\Support\Facades\Log;
use BookStack\Util\CspService;

$approvers = array();
function getApproverIDs() {
  global $approvers;
  $approvers = array();
  // This could be cached in the future
  $roles = Role::whereIn('display_name', array("Wiki Approver"))->get()->all();
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
    $cc = array_map(function($c) { return ["html" => $c->html, "author" => $c['updated_by'], "timestamp" => $c->updated_at->timestamp]; }, $cc);

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
    $result['url'] = $page->getUrl();
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
    $approval_timestamp = null;
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
          $approval_timestamp = $c["timestamp"];
        }
      }
    }
    return array(
      "approved_revision" => $latest_approved,
      "approval_timestamp" => $approval_timestamp,
      "approvals" => $revs_approval,
    );
  }
}


function approvalThresh($page) {
  // Return the number of approvals needed for the given page, or 0 if none are needed.
  foreach ($page->tags as $tag) {
    if (strpos($tag->name, 'maint_') === 0) {
      return 1; // Just one approval needed
    }
  }
  $APPROVAL_RE = getenv("PAGE_APPROVAL_REGEXP", "/tools\\/*/");
  if (preg_match($APPROVAL_RE, $page->getUrl(), $matches)) {
    return Approval::DEFAULT_APPROVAL_THRESH;
  }
  return 0;
}

Theme::listen(ThemeEvents::ROUTES_REGISTER_WEB, function (Router $router) {
  Log::info("Prefetching approver IDs");
  getApproverIDs();
  Log::info("Registering Protohaven custom routes");

  $router->get('/approvals/{book_slug}/{page_slug}/{rev_id}', function ($book_slug, $page_slug, $rev_id) {
    $pq = new PageQueries();
    $page = $pq->findVisibleBySlugsOrFail($book_slug, $page_slug);
    $thresh = approvalThresh($page);
    if ($thresh > 0) {
      Log::info($page->id);
      echo json_encode(Approval::getPageState($page, (int)$rev_id, $thresh));
    } else {
      echo json_encode(["ignore" => true]);
    }
  });

  $router->get('/approvals', function () {
    $nonce = app()->make(CspService::class)->getNonce();
    $items = [];
    $uniqueTags = [];
    foreach (Page::select('*')->get()->all() as $page) {
      if (!$page->slug) continue; // Skip book headers

      $thresh = approvalThresh($page);
      if ($thresh <= 0) continue;

      $state = Approval::getPageState($page, 0, $thresh);
      if ($state['current_revision'] == $state['approved_revision'] || $state['approved_revision'] == "all") continue;

      $needed = $state['thresh'] - count($state['approvals'][$state['current_revision']] ?? []);
      $chapname = $page->chapter()->first()->name ?? '';
      $book = $page->book()->first();
      $items[] = [$book, $chapname, $page, $needed, $state['approved_revision']];

      foreach ($page->tags as $tag) {
          $uniqueTags["{$tag->name}=" . strtoupper($tag->value)] = true;
      }
    }
    ?>
    <!DOCTYPE html>
    <html>
      <head>
      </head>
      <body>
    <h2>Page approvals process:</h2>
    <p>The following pages need approvals and will display a disclaimer until approved. Approvals may be given by anyone with the "Wiki Approver" role.</p>
    <p>To approve e.g. revision 3, comment "Approve #3" in the page comments. Approvers can also comment "Reject #3" to reset approvals.</p>
    <p>To exclude permanently: "Approve #forever".</p>
    <p>Only books/pages matching $PAGE_APPROVAL_REGEXP are enrolled; see <a href="https://github.com/protohaven/server_config/" target="_blank">server_config</a> for details.</p>
    <hr/>
    <h2>Pages requiring approval:</h2>
    <select id="approval_tags">
        <option value="">Filter...</option>
        <?php foreach(array_keys($uniqueTags) as $tagPair): ?>
            <option value="<?= htmlentities($tagPair) ?>"><?= htmlentities($tagPair) ?></option>
        <?php endforeach; ?>
    </select>
    <?php foreach ($items as [$book, $chapname, $page, $needed, $ar]): ?>
    <div class="item" style="padding:14px;margin:14px;border:1px grey solid;border-radius:3px;"
        <?php foreach($page->tags as $tag): ?>
        data-tag-<?= $tag->name ?>="<?= strtoupper($tag->value) ?>"
        <?php endforeach; ?>>
        <p><strong>
            <a href="<?= $page->getUrl() ?>" target="blank">
                <?= "$book->name / $chapname / $page->name (#$page->id) rev {$state['current_revision']}" ?>
            </a>
        </strong></p>
        <ul>
            <?php foreach($page->tags as $tag): ?>
            <li><?= "{$tag->name} = {$tag->value}" ?></li>
            <?php endforeach; ?>
        </ul>
        <p>Approvals needed: <?= $needed ?></p>
        <?php if($ar): ?>
        <p>Last approved: <a href="<?= "{$page->getUrl()}/revisions/$ar" ?>" target="blank">rev <?= $ar ?></a></p>
        <?php endif; ?>
    </div>
    <?php endforeach; ?>
    </body>
    <script nonce="<?= $nonce ?>">
      document.getElementById('approval_tags').addEventListener('change', (e) => {
        let nv = e.target.value ? e.target.value.split('=') : [null, null];
        document.querySelectorAll(".item").forEach(el => {
          el.style.display = nv[0] === null ? 'block' : 'none';
        });
        document.querySelectorAll(`[data-tag-${nv[0]}="${nv[1]}"]`).forEach(el => {
          el.style.display = 'block';
        });
      });
    </script>
    </html>
<?php });

});

?>
