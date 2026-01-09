<script lang="ts">
  import { onMount } from 'svelte';
  import { Alert, Card, CardBody, CardTitle, Button, Input, FormGroup, Label, Accordion, AccordionItem, Spinner } from '@sveltestrap/sveltestrap';
  import { open_ws } from '../api';
  import { get } from '$lib/api';

  import { isodate } from '$lib/api';
  let endDate = isodate(new Date());
  let startDate = isodate(new Date(new Date().setDate(new Date().getDate() - 30)));
  let channels = {};
  export let visible;
  export let user;

  async function fetchChannels() {
    try {
      const response = await get('/staff/discord_member_channels');
      console.log(response);
      channels = Object.fromEntries(response.map(entry => [entry, false]));
    } catch (error) {
      alert('Failed to fetch channels:', error);
    }
  }
  onMount(() => {
      fetchChannels();
  });

  $: {
    if (visible && !channels) {
      fetchChannels();
    }
  }

  function selectAll() {
    channels = Object.fromEntries(Object.keys(channels).map(entry => [entry, true]));
  }

  function selectNone() {
    channels = Object.fromEntries(Object.keys(channels).map(entry => [entry, false]));
  }

  let messageLog = {};
  let mediaLog = {};
  let channel_summaries = [];
  let final_summary = "";

  let lastreload = null;
  function maybeReload(force=false) {
      const now = new Date().getTime();
      if (!lastreload || force || (now - lastreload) > 500) {
          messageLog = messageLog;
          channel_summaries = channel_summaries;
          mediaLog = mediaLog;
          lastreload = now;
      }
  }

  let submitting = false;
  const handleSubmit = () => {
    submitting = true;
    messageLog = {};
    mediaLog = {};
    channel_summaries = [];
    final_summary = "";
    const socket = open_ws('/staff/summarize_discord');
    socket.onopen = () => {
      socket.send(JSON.stringify({
        start_date: startDate,
        end_date: endDate,
        channels: Object.keys(channels).filter(key => channels[key] === true),
      }));
    };

    socket.onmessage = (m) => {
      let d = JSON.parse(m.data);
      if (messageLog[d.channel] === undefined) {
        messageLog[d.channel] = []
      }
      if (d.type === 'individual') {
        messageLog[d.channel].push(`${d.created_at} ${d.author}: ${d.content}`);
        console.log(d.links);
        for (let l of d.images) {
          if (!mediaLog[d.channel]) {
            mediaLog[d.channel] = [];
          }
          mediaLog[d.channel].push({author: d.author, ref: d.ref, link: l, type: 'image'})
        }
        for (let l of d.videos) {
          if (!mediaLog[d.channel]) {
            mediaLog[d.channel] = [];
          }
          mediaLog[d.channel].push({author: d.author, ref: d.ref, link: l, type: 'video'})
        }
      } else if (d.type === 'channel_summary') {
        channel_summaries[d.channel] = d.content;
      } else if (d.type === 'final_summary') {
        final_summary = d.content;
      }
      maybeReload();
    };

    socket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    socket.onclose = () => {
      console.log('WebSocket connection closed, doing final reload');
      maybeReload(true);
      submitting = false;
    };
  };
</script>

<style>
  .checkbox-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 10px;
  }
  .thumb {
      max-width: 480px;
      max-height: 480px;
  }
</style>

{#if visible}
<Card>
  <CardBody>
    <CardTitle>Discord Summarizer</CardTitle>
    <p>
      Select a time range and and list of channels, and receive a summary for newsletter or other media purpose.
    </p>

    {#if !user}
    <Alert color="warning">You must be logged in to use this tool</Alert>
    {/if}

    <FormGroup>
      <Label for="startDate">Start Date</Label>
      <Input type="date" id="startDate" bind:value={startDate} />
    </FormGroup>
    <FormGroup>
      <Label for="endDate">End Date</Label>
      <Input type="date" id="endDate" bind:value={endDate} />
    </FormGroup>
    <FormGroup>
      <Label>Discord Channels</Label>
      <Button on:click="{selectAll}">Select All</Button>
      <Button on:click="{selectNone}">Select None</Button>
      <div class="checkbox-grid">
        {#each Object.keys(channels) as label}
          <div>
            <input type="checkbox" id={label} value={label} bind:checked={channels[label]} />
            <Label for={label}>{label}</Label>
          </div>
        {/each}
      </div>
    </FormGroup>
    <Button on:click={handleSubmit} disabled={submitting}>Submit</Button>
    {#if submitting}
    <Spinner/>
    {/if}


    <h5>Message Logs:</h5>
    {#each Object.entries(messageLog) as [channel, messages]}
      <Accordion stayOpen>
        <AccordionItem header={channel}>
          <div style="max-height: 200px; overflow-y: auto;">
            {#each messages as message}
              <p>{message}</p>
            {/each}
          </div>
        </AccordionItem>
      </Accordion>
    {/each}
    <h5>Channel Summaries:</h5>
    {#each Object.keys(channel_summaries) as channel}
      <h5>{channel}</h5>
      <p>{channel_summaries[channel]}</p>
    {/each}
    <h5>Final Summary:</h5>
    {@html final_summary}
    <h5>Media</h5>
    {#each Object.keys(mediaLog) as channel}
      <strong>{channel}</strong>
      {#each mediaLog[channel] as l}
      <p>
        <a href={l.ref} target="_blank">
          {#if l.type == 'image'}
            <img class="thumb" src={l.link}/>
          {:else}
            <video class="thumb" controls>
              <source src="{l.link}" type="video/mp4">
              Your browser does not support the video tag.
            </video>
          {/if}
        </a>
        <em>Credit <a href={l.ref} target="_blank">{l.author}</a></em>
      </p>
      {/each}
    {/each}
  </CardBody>
</Card>
{/if}
