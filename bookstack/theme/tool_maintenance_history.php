<?php
use BookStack\Entities\Queries\PageQueries;
use BookStack\Entities\Models\Book;
use BookStack\Entities\Models\Page;
use BookStack\Theming\ThemeEvents;
use BookStack\Facades\Theme;
use Illuminate\Routing\Router;
use BookStack\Users\Models\Role;
use Illuminate\Support\Facades\Log;

function getToolMaintenanceData($tool_code) {
  return Http::withHeaders(["X-Protohaven-APIKey" => getenv("PROTOHAVEN_API_KEY")])->get(getenv("PROTOHAVEN_API_URL") . "/admin/get_maintenance_data")->throw()->json();
}

function loadToolData($page) {
  $TOOL_TAGS = ["maint_task", "tool_code", "maint_freq_days", "maint_asana_section", "maint_ref", "maint_level"];
  $tags = $page->tags()->get()->all();
  $result = [];
  foreach ($tags as $t) {
    if (in_array($t['name'], $TOOL_TAGS)) {
      $result[$t['name']] = $t['value'];
    }
  }
  return $result;
}

function loadToolCode($page) {
  $tags = $page->tags()->get()->all();
  $result = [];
  foreach ($tags as $t) {
    if ($t['name'] == "tool_code") {
      return $t['value'];
    }
  }
  return null;
}

Theme::listen(ThemeEvents::ROUTES_REGISTER_WEB, function (Router $router) {
  $router->get('/maintenance_history/{book_slug}/{page_slug}', function ($book_slug, $page_slug) {
    $pq = new PageQueries();
    $page = $pq->findVisibleBySlugsOrFail($book_slug, $page_slug);
    Log::info($page->id);
    $tool = loadToolCode($page);
    if (!$tool) {
      return response("tool_code not found in tags", 404);
    }
    return json_encode(getToolMaintenanceData($tool));
  });

  $router->get('/maintenance_data/{book_slug}', function ($book_slug) {
    $book = Book::where('slug', $book_slug)->get()->first();
    if (!$book) {
      return response("Book with slug $book_slug not found", 404);
    }
    $result = [];
    foreach ($book->pages()->get()->all() as $page) {
      $td = loadToolData($page);
      if ($td) {
        $td['book_slug'] = $book->slug;
        $td['page_slug'] = $page->slug;
        $td['approval_state'] = Approval::getPageState($page, 0);
        $result[] = $td;
      }
    }
    return json_encode($result);
  });
});
?>
