<script type="ts">
import {get, post} from '$lib/api.ts';
import FetchError from './fetch_error.svelte';
export let email;

promise = get("/calendar?email="+email);
onMount(() => {
});
let promise = Promise.resolve((resolve, reject)=>{});
</script>

{#await promise}
  <Spinner/>
{:then p}
  <div>
  	{JSON.stringify(p)}
  </div>
{:catch error}
  <FetchError {error}/>
{/await}

