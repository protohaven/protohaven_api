<?php
use BookStack\Theming\ThemeEvents;
use BookStack\Facades\Theme;
use Illuminate\Routing\Router;
use Illuminate\Support\Facades\Log;
use PHPUnit\Framework\TestCase;

require_once("approvals.php");


function testExtractCommand() {
  assert_equal(Approval::extractCommand("Random comment"), null, "Random comment ignored");
  assert_equal(Approval::extractCommand("Random comment with Approve in the text"), null, "Approve without rev ignored");
  assert_equal(Approval::extractCommand("foo Approve #123 bar"), ["action" => "approve", "rev" => 123], "inline approve");
  assert_equal(Approval::extractCommand("foo\n\nbar ApPrOve #123\n baz"), ["action" => "approve", "rev" => 123], "case insensitive approve");
  assert_equal(Approval::extractCommand("reject #456"), ["action" => "reject", "rev" => 456], "reject");
  assert_equal(Approval::extractCommand("approve #forever"), ["action" => "approve", "rev" => "all"], "approve forever");
}

function testResolveState() {
  $got = Approval::resolveState([["author" => 1, "html" => "approve #1"]], [1 => true], 2);
  assert_equal($got, ["approved_revision" => null, "approvals" => [1 => [1]]], "Single approval (insufficient)");

  $got = Approval::resolveState([["author" => 1, "html" => "approve #1"]], [1 => true], 1);
  assert_equal($got, ["approved_revision" => 1, "approvals" => [1 => [1]]], "Single approval (sufficient)");

  $got = Approval::resolveState([
    ["author" => 1, "html" => "approve #1"],
    ["author" => 2, "html" => "approve #1"],
  ], [1 => true, 2 => true], 2);
  assert_equal($got, ["approved_revision" => 1, "approvals" => [1 => [1, 2]]], "Two separate approvers");

  $got = Approval::resolveState([
    ["author" => 1, "html" => "approve #1"],
  ], [], 2);
  assert_equal($got, ["approved_revision" => null, "approvals" => []], "Non-approver not counted");

  $got = Approval::resolveState([
    ["author" => 1, "html" => "approve #1"],
    ["author" => 2, "html" => "approve #2"],
  ], [1 => true, 2 => true], 2);
  assert_equal($got, ["approved_revision" => null, "approvals" => [1 => [1], 2 => [2]]], "Different revs don't accumulate approvals");

  $got = Approval::resolveState([
    ["author" => 1, "html" => "approve #1"],
    ["author" => 2, "html" => "reject #1"],
    ["author" => 2, "html" => "approve #1"],
  ], [1 => true, 2 => true], 2);
  assert_equal($got, ["approved_revision" => null, "approvals" => [1 => [2]]], "Rejection by different approver resets count");

  $got = Approval::resolveState([
    ["author" => 1, "html" => "approve #1"],
    ["author" => 2, "html" => "approve #1"],
    ["author" => 3, "html" => "reject #1"],
  ], [1 => true, 2 => true], 2);
  assert_equal($got, ["approved_revision" => 1, "approvals" => [1 => [1,2]]], "Rejection ignored if not an approver");

  $got = Approval::resolveState([
    ["author" => 1, "html" => "approve #1"],
    ["author" => 2, "html" => "approve #1"],
    ["author" => 1, "html" => "approve #2"],
    ["author" => 2, "html" => "approve #2"],
  ], [1 => true, 2 => true], 2);
  assert_equal($got, ["approved_revision" => 2, "approvals" => [1 => [1, 2], 2 => [1, 2]]], "Second rev approval overwrites first");

  $got = Approval::resolveState([
    ["author" => 1, "html" => "approve #forever"],
    ["author" => 2, "html" => "disapprove #1"],
  ], [1 => true, 2 => true], 2);
  assert_equal($got, ["approved_revision" => "all", "approvals" => []], "Permanent approval");
}


Theme::listen(ThemeEvents::ROUTES_REGISTER_WEB, function (Router $router) {
  $router->get('/unittest/approvals', function () {
    testExtractCommand();
    testResolveState();
    echo "ALL TESTS PASS";
  });
});
?>
