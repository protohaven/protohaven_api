<script type="typescript" lang="ts">
	export let tool_state: ToolStateChartItem[] | null = null;

	interface ToolStateChartItem {
		status: string;
		docs_err?: boolean;
		clearance_doc?: { status: string } | null;
		tutorial_doc?: { status: string } | null;
	}

	interface Segment {
		label: string;
		count: number;
		pct: number;
		color: string;
	}

	const TOOL_STATUSES = [
		{ label: 'Red', color: 'danger' },
		{ label: 'Yellow', color: 'warning' },
		{ label: 'Blue', color: 'info' },
		{ label: 'Green', color: 'success' },
		{ label: 'Unknown', color: 'secondary' }
	];

	const DOC_STATUSES = [
		{ label: 'Missing', color: 'danger' },
		{ label: 'No approval', color: 'warning' },
		{ label: 'Approved', color: 'success' }
	];

	function tool_status_label(status: string) {
		const s = status.toLowerCase();
		if (s.startsWith('red')) {
			return 'Red';
		}
		if (s.startsWith('yellow')) {
			return 'Yellow';
		}
		if (s.startsWith('blue')) {
			return 'Blue';
		}
		if (s.startsWith('green')) {
			return 'Green';
		}
		return 'Unknown';
	}

	function doc_status_label(doc?: { status: string } | null) {
		if (!doc) {
			return null;
		}
		if (doc.status === 'approved') {
			return 'Approved';
		}
		if (doc.status === 'missing') {
			return 'Missing';
		}
		return 'No approval';
	}

	function build_tool_segments(tools: ToolStateChartItem[]): Segment[] {
		const counts = new Map(TOOL_STATUSES.map(({ label }) => [label, 0]));
		for (const tool of tools) {
			const label = tool_status_label(tool.status);
			counts.set(label, (counts.get(label) || 0) + 1);
		}
		const total = tools.length;
		return TOOL_STATUSES.map(({ label, color }) => {
			const count = counts.get(label) || 0;
			return {
				label,
				color,
				count,
				pct: total > 0 ? (count / total) * 100 : 0
			};
		});
	}

	function build_doc_segments(tools: ToolStateChartItem[]): Segment[] {
		const counts = new Map(DOC_STATUSES.map(({ label }) => [label, 0]));
		for (const tool of tools) {
			for (const doc of [tool.clearance_doc, tool.tutorial_doc]) {
				const label = doc_status_label(doc);
				if (label) {
					counts.set(label, (counts.get(label) || 0) + 1);
				}
			}
		}
		const total = tools.length * 2;
		return DOC_STATUSES.map(({ label, color }) => {
			const count = counts.get(label) || 0;
			return {
				label,
				color,
				count,
				pct: total > 0 ? (count / total) * 100 : 0
			};
		});
	}

	$: tools = tool_state || [];
	$: docs_err = tools.some((tool) => tool.docs_err);
	$: tool_segments = build_tool_segments(tools);
	$: doc_segments = docs_err ? [] : build_doc_segments(tools);
</script>

{#if tools.length > 0}
	<section class="tool-state-charts mb-3" aria-label="Tool and documentation completion levels">
		<h5 class="h6">Completion levels</h5>
		<div class="tool-state-chart">
			<div class="d-flex justify-content-between">
				<span>Tools</span>
				<span>{tools.length} total</span>
			</div>
			<div
				class="tool-state-chart-bar d-flex"
				role="img"
				aria-label="Tool states stacked bar chart"
			>
				{#each tool_segments as seg}
					<div
						class="tool-state-chart-segment bg-{seg.color}"
						style="width:{seg.pct}%;"
						title="{seg.label}: {seg.count}"
					></div>
				{/each}
			</div>
			<div class="tool-state-chart-legend d-flex flex-wrap gap-2 mt-1">
				{#each tool_segments as seg}
					<span class="me-2"><span class="badge bg-{seg.color}">{seg.count}</span> {seg.label}</span
					>
				{/each}
			</div>
		</div>
		<div class="tool-state-chart mt-2">
			<div class="d-flex justify-content-between">
				<span>Tool docs</span>
				<span>{tools.length * 2} total</span>
			</div>
			{#if docs_err}
				<em>Documentation status unavailable</em>
			{:else}
				<div
					class="tool-state-chart-bar d-flex"
					role="img"
					aria-label="Tool documentation states stacked bar chart"
				>
					{#each doc_segments as seg}
						<div
							class="tool-state-chart-segment bg-{seg.color}"
							style="width:{seg.pct}%;"
							title="{seg.label}: {seg.count}"
						></div>
					{/each}
				</div>
				<div class="tool-state-chart-legend d-flex flex-wrap gap-2 mt-1">
					{#each doc_segments as seg}
						<span class="me-2"
							><span class="badge bg-{seg.color}">{seg.count}</span> {seg.label}</span
						>
					{/each}
				</div>
			{/if}
		</div>
	</section>
{/if}

<style>
	.tool-state-chart-bar {
		height: 1.5rem;
		border-radius: 0.25rem;
		overflow: hidden;
	}

	.tool-state-chart-segment {
		height: 100%;
		min-width: 0;
	}
</style>
