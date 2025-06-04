<?php
use BookStack\Entities\Queries\PageQueries;
use BookStack\Entities\Models\Book;
use BookStack\Entities\Models\Page;
use BookStack\Theming\ThemeEvents;
use BookStack\Facades\Theme;
use Illuminate\Routing\Router;
use BookStack\Users\Models\Role;
use BookStack\Activity\Models\Tag;
use Illuminate\Support\Facades\Log;
use Illuminate\Http\Request;

function getPageCategory($page) {
  $CLEARANCE_BOOKS = explode(',', getenv('PH_TOOL_LINK_CLEARANCE_BOOKS') ?: "clearances");
  $TOOL_TUTORIAL_BOOKS = explode(',', getenv('PH_TOOL_LINK_TUTORIAL_BOOKS') ?: "tool-guides");
  $book_slug = $page['book']['slug'];
  if (in_array($book_slug, $CLEARANCE_BOOKS)) {
    return "clearance";
  } elseif (in_array($book_slug, $TOOL_TUTORIAL_BOOKS)) {
    return "tool_tutorial";
  } else {
    return "other";
  }
}

function getPageURLsWithToolCode($tool_code) {
  $tags = Tag::where('name', 'tool_code')
    # Note that this variable binding use of whereRaw prevents
    # sql injection - see https://stackoverflow.com/a/78014344
    ->whereRaw('LOWER(value) = ?', [trim(strtolower($tool_code))])
    ->with('entity')
    ->with('entity.book')
    ->get();
  $result = array();
  foreach ($tags as $tag) {
    // Log::info($tag);
    $page = $tag->entity ?? null;
    if ($page instanceof \BookStack\Entities\Models\Page) {
      $result[getPageCategory($page)] = $page->getUrl();
    }
  }
  return $result;
}

function clearance_not_found_url() {
    return getenv("PH_TOOL_LINK_CLEARANCE_NOT_FOUND_URL") ?: "/books/clearances/page/missing-clearance-page";
}

function tutorial_not_found_url() {
    return getenv("PH_TOOL_LINK_TUTORIAL_NOT_FOUND_URL") ?: "/books/tool-guides/page/tool-guide-missing";
}

Theme::listen(ThemeEvents::ROUTES_REGISTER_WEB, function (Router $router) {

  $router->get('/tool_clearance/{tool_code}', function ($tool_code) {
    $urls = getPageURLsWithToolCode($tool_code);
    return redirect($urls['clearance'] ?? clearance_not_found_url());
  });

  $router->get('/tool_tutorial/{tool_code}', function ($tool_code) {
    $urls = getPageURLsWithToolCode($tool_code);
    return redirect($urls['tool_tutorial'] ?? tutorial_not_found_url());
  });

  $router->get('/tool_docs_report', function() {
    $tags = Tag::where('name', 'tool_code')
      ->whereNotNull('value')
      ->with('entity')
      ->with('entity.book')
      ->get();
    $result = array();
    $approval_result = array();
    foreach ($tags as $tag) {
      $page = $tag->entity ?? null;
      $book_slug = $page['book']['slug'];
      if ($page instanceof \BookStack\Entities\Models\Page) {
        $code = strtoupper($tag["value"]);
        $state = Approval::getPageState($page, 0, Approval::DEFAULT_APPROVAL_THRESH);
        $result[$code][getPageCategory($page)][] = $state;
      }
    }
    echo json_encode([
      "by_code" => $result,
      "clearance_not_found_url" => clearance_not_found_url(),
      "tutorial_not_found_url" => tutorial_not_found_url()
    ]);
  });
});

?>
