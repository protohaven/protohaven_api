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


function getPageURLsWithToolCode($tool_code) {
  $CLEARANCE_BOOKS = ["basic-maintenance"];
  $TOOL_TUTORIAL_BOOKS = ["test"];
  $tags = Tag::where('name', 'tool_code')
    ->where('value', $tool_code)
    ->with('entity')
    ->with('entity.book')
    ->get();
  $result = array();
  foreach ($tags as $tag) {
    // Log::info($tag);
    $page = $tag->entity ?? null;
    $book_slug = $page['book']['slug'];
    if ($page instanceof \BookStack\Entities\Models\Page) {
      if (in_array($book_slug, $CLEARANCE_BOOKS)) {
        $result["clearance"] = $page->getUrl();
      } elseif (in_array($book_slug, $TOOL_TUTORIAL_BOOKS)) {
        $result["tool_tutorial"] = $page->getUrl();
      }
    }
  }
  return $result;
}


Theme::listen(ThemeEvents::ROUTES_REGISTER_WEB, function (Router $router) {

  $router->get('/tool_clearance/{tool_code}', function ($tool_code) {
    $NOTFOUND_URL = "/book/test/page/herp";
    $urls = getPageURLsWithToolCode($tool_code);
    return redirect($urls['clearance'] ?? $NOTFOUND_URL);
  });

  $router->get('/tool_tutorial/{tool_code}', function ($tool_code) {
    $NOTFOUND_URL = "/book/test/page/herp";
    $urls = getPageURLsWithToolCode($tool_code);
    return redirect($urls['tool_tutorial'] ?? $NOTFOUND_URL);
  });
});

?>
