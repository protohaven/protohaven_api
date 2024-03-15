<script type="ts">
  import '../app.scss';

	import { Row, Card, Container } from '@sveltestrap/sveltestrap';

  import TestComponent from '$lib/test_component.svelte';
  import Splash from '$lib/splash.svelte';
  import SigninOk from '$lib/signin_ok.svelte';
  import MembershipExpired from '$lib/membership_expired.svelte';
	import Waiver from '$lib/waiver.svelte';
  let state='splash';
  let name='member';
	let email=null;
	let person='member';
	let checking=false;
	let waiver=false;
  let dependent_info="";
	let feedback=null;

	async function on_splash_submit(p) {
		person = p;
		return await submit();
	}

	async function waiver_agreed() {
		waiver=true;
		return await submit();
	}

  function on_signin_return(survey_response) {
    if (survey_response) {
      console.error(survey_response);
      alert("TODO survey response");
    }
    state = 'splash';
  }

  async function submit() {
    checking = true;
    const res = await fetch('http://localhost:5000/welcome', {
      method: 'POST',
      body: JSON.stringify({email, person, waiver, dependent_info}),
      headers: {
        'Content-type': 'application/json',
      },
    });
    checking = false;
    if (res.ok) {
      let result = await res.json();
			console.log(result);
			if (result.notfound) {
				feedback = "Member not found; please try again";
				return;
			}
			name = result.firstname;
			if (!result.waiver_signed) {
				state = 'waiver';
			}
			else if (person == 'guest' || result.status == 'Active') {
				state = 'signin_ok';
				waiver = false;
				feedback = null;
			} else {
				state = 'membership_expired';
			}
    } else {
      alert("TODO handle error" + e.toString());
    }
  }
</script>

<main>
	<Row class="mb-5">
		<img src="logo_color.svg"/>
	</Row>
	<Row>
    {#if state == 'splash'}
      <Splash bind:email={email} bind:dependent_info={dependent_info} {feedback} {checking} on_member={()=>on_splash_submit('member')} on_guest={()=>on_splash_submit('guest')}/>
    {:else if state == 'waiver' }
      <Waiver name={name} on_submit={waiver_agreed}/>
    {:else if state == 'membership_expired' }
      <MembershipExpired name={name} on_close={() => {state = 'splash'}}/>
    {:else if state == 'signin_ok'}
      <SigninOk {name} guest={person == 'guest'} on_close={on_signin_return}/>
    {/if}
	</Row>
</main>


<style>
		img {
			max-width: 600px;
			margin-left: auto;
			margin-right: auto;
		}
		main {
			width: 100%;
			max-width: 800px;
			padding: 15px;
			margin: 0 auto;
		}
</style>
