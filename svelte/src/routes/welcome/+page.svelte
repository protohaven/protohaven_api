<script type="typescript">
  import '../../app.scss';
  import { onMount } from 'svelte';
  import {base_ws, get, post, open_ws} from '$lib/api.ts';
  import { Row, Card, Container } from '@sveltestrap/sveltestrap';
  import Splash from '$lib/splash.svelte';
  import SigninOk from '$lib/signin_ok.svelte';
  import MembershipExpired from '$lib/membership_expired.svelte';
	import Waiver from '$lib/waiver.svelte';
  let state='splash';
  let name='member';
  let email=null;
  let person='member';
  let checking=false;
  let progress=null;
  let waiver_ack=false;
  let dependent_info="";
	let feedback=null;
  let referrer = "";
  let testing = false;

  let announcements = [];
  let violations = [];

  onMount(() => {
    console.log("Base WS:", base_ws());
    if (new URLSearchParams(window.location.search).get('testing')) {
      testing = true;
      console.log("testing mode enabled; test announcements will be fetched");
    }
  });


  async function on_splash_submit(p) {
    person = p;
    return await submit();
  }

  async function waiver_agreed() {
    waiver_ack=true;
    return await submit();
  }

  function do_post(silent=false) {
    // We capture the data at the time of invocation to prevent data from getting cleared asynchronously
    let capture = JSON.stringify({email, person, waiver_ack, dependent_info, referrer, testing});
    return new Promise((resolve, reject) => {
      const socket = open_ws("/welcome/ws")
      socket.addEventListener("open", (event) => {
        socket.send(capture);
      });
      if (silent) {
      	resolve(null);
      } else {
	      socket.addEventListener("message", (event) => {
          let data = JSON.parse(event.data);
          if (data.pct !== undefined) {
            progress = data;
          } else {
            progress = null;
            resolve(data);
          }
        });
      }
    });
  }


  function restart_flow() {
    email = null;
    person = 'member';
    waiver_ack = false;
    referrer = '';
    feedback = null;
    state = 'splash';
    announcements = [];
    violations = [];
  }

  function on_signin_return(survey_response) {
    if (survey_response) {
      referrer = survey_response;
    } else {
      referrer = "Not provided";
    }
    // We fire the guest registration off into the void and move on
    if (person == 'guest') {
      do_post(false); // Silently
    }
    if (person !== 'guest' && announcements) { // Acknowledge announcements
      post('/welcome/announcement_ack', {email});
    }

    restart_flow();
  }

  async function submit() {
    checking = true;
    let result = await do_post();
    checking = false;
    if (result.notfound) {
      feedback = "Member not found; please try again";
      return;
    }
    name = result.firstname;
    announcements = result.announcements;
    violations = result.violations;

    if (person !== 'guest' && result.status !== 'Active') {
      // Expired membership takes priority in notification
      state = 'membership_expired';
      return;
    }

    if (!result.waiver_signed) {
      state = 'waiver';
      return;
    }

    // If everything else is good, we're good.
    state = 'signin_ok';
  }
</script>

<main>
	<Row class="mb-5">
		<img src="logo_color.svg" alt="logo"/>
	</Row>
	<Row class="d-flex justify-content-center" style="max-width: 920px">
    {#if state == 'splash'}
      <Splash bind:email={email} bind:dependent_info={dependent_info} {feedback} {progress} on_member={()=>on_splash_submit('member')} on_guest={()=>on_splash_submit('guest')}/>
    {:else if state == 'waiver' }
      <Waiver name={name} on_submit={waiver_agreed} checking={checking}/>
    {:else if state == 'membership_expired' }
      <MembershipExpired name={name} on_close={restart_flow}/>
    {:else if state == 'signin_ok'}
      <SigninOk {name} {email} guest={person == 'guest'} {announcements} {violations} on_close={on_signin_return}/>
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
			padding: 15px;
			margin: 0 auto;

			display: -ms-flexbox;
			display: -webkit-box;
			display: flex;
			flex-direction: column;
			-ms-flex-align: center;
			-ms-flex-pack: center;
			-webkit-box-align: center;
			align-items: center;
			-webkit-box-pack: center;
			justify-content: center;
			padding-top: 40px;
			padding-bottom: 40px;
  			background-color: #f8f8f8;
		}
</style>
