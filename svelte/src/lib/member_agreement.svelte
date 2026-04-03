<script type="typescript">
	import { Row, Col, Card, Button, Spinner } from '@sveltestrap/sveltestrap';
	export let on_submit;
	export let checking;
</script>

<Card>
	<h2 class="my-4 text-center">Protohaven Member Agreement</h2>
  <Row class="justify-content-center text-center">
    <em>Published 2024-03-14</em>
  </Row>
	<Card class="m4 p4" style="overflow-y:scroll; max-height: 400px">
    <p>This Member Agreement (“Agreement”) is entered into between Protohaven, a Pennsylvania nonprofit organization located in Wilkinsburg, PA (“Protohaven”), and the undersigned individual (“Member”).</p>
    <p>By executing this Agreement, the Member acknowledges, understands, and consents to all terms and conditions herein.</p>
    <p>1. Purpose and Scope</p>
    <p>Protohaven operates and maintains a nonprofit makerspace that provides shared access to tools, equipment, and collaborative work areas for creative, technical, and educational projects. This Agreement establishes the binding responsibilities, expectations, and safety requirements that govern the Member’s access to and use of Protohaven facilities and resources.</p>
    <p>2. Membership Eligibility and Good Standing</p>
    <p>To qualify for membership, an individual must satisfy the following criteria:</p>
    <p>Age Requirement: The individual must be eighteen (18) years of age or older. Any individual under the age of eighteen (18) is required to have a Minor Participation Waiver executed by a parent or legal guardian to access the facility.</p>
    <p>Training & Fees: The individual must successfully complete all required orientation, training, and safety classes, and must pay all required membership fees.</p>
    <p>For the duration of this Agreement, the Member must remain in Good Standing. Good Standing is defined as the Member's full compliance with all provisions of this Agreement, the Code of Conduct, and the timely payment of all required membership fees.</p>
    <p>3. Code of Conduct and Enforcement</p>
    <p>The Member agrees to strictly adhere to the Protohaven Code of Conduct, which encompasses the organization’s Core Values, Community Guidelines, Safety Rules, Non-Discrimination Policy, and Anti-Harassment Policy.</p>
    <p>3.1. Violations and Sanctions</p>
    <p>Any Member or guest who violates the Code of Conduct will be directed to cease the behavior or immediately vacate the premises. All violations will be formally documented by Protohaven Staff, Shop Technicians, or a Member of the Board of Directors.</p>
    <p>Based on the severity or recurrence of documented violations, the Protohaven Board of Directors reserves the absolute right to suspend or terminate the Member’s access and membership. Notice of such suspension or termination shall be provided to the Member in writing. Furthermore, any instance of unsafe tool or equipment operation may result in the immediate removal of the Member’s operational clearances, requiring the Member to complete remedial training, including classes or private instruction, at their own expense.</p>
    <p>3.2. Appeal Process</p>
    <p>A Member may formally appeal a suspension or termination of membership by submitting a written request to the Board of Directors within thirty (30) calendar days of receiving the notification. The Member’s suspension or termination shall remain in effect until the appeal process is concluded.</p>
    <p>4. Safety and Equipment Operation</p>
    <p>The Member assumes a personal duty to prioritize safety and must comply with all Protohaven safety regulations. This includes, but is not limited to:</p>
    <p>Personal Protective Equipment (PPE): Wear all required PPE (e.g., safety goggles, gloves, hearing protection) in designated areas at all times.</p>
    <p>Training and Clearance: Only operate equipment after successfully completing the requisite training and possessing the necessary operational Clearance.</p>
    <p>Impairment and Safety Systems: It is strictly prohibited to operate equipment while impaired by drugs, alcohol, or fatigue, or to override any established safety systems.</p>
    <p>Machine Monitoring: Never leave active machinery unattended.</p>
    <p>Reporting: Immediately report any equipment damage or the discovery of unsafe conditions to Protohaven staff.</p>
    <p>5. Equipment Use Policy</p>
    <p>All equipment is provided on a shared basis. Members may reserve equipment via the Member Dashboard. Independent operation of any tool or equipment requires a valid operational Clearance. Members are prohibited from independently using equipment for which they lack Clearance; however, such equipment may be used with the direct supervision and assistance of a cleared individual. The Member is required to abide by the Equipment Damage Policy at all times.</p>
    <p>6. Personal Property and Storage</p>
    <p>The Member is solely responsible for the security, labeling, and timely removal of all personal materials, projects, and property. Protohaven explicitly disclaims all liability for any personal property that is lost, stolen, or damaged within the facility. Projects or materials left beyond the posted storage limits or deadlines will be subject to removal or disposal at Protohaven's discretion without further notice.</p>
    <p>7. Intellectual Property (IP)</p>
    <p>The Member retains full ownership of all intellectual property created within the makerspace, unless a separate, written agreement states otherwise. The Member is obligated to respect the intellectual property rights of all other Members and third parties.</p>
    <p>Protohaven reserves the right to capture and utilize photographs or video footage of the facility and general activities for promotional purposes. The Member has the right to opt out of the use of their image for promotional material by providing written notice to Protohaven.</p>
    <p>8. Fees, Payment, and Access</p>
    <p>Membership fees must be paid promptly in accordance with Protohaven's current posted policies. Except where required by applicable law or determined at the sole discretion of Protohaven, all fees are non-refundable. Failure to remit required fees may result in the immediate suspension of the Member's access to the facility and resources. The Member may cancel their membership at any time through the Membership Dashboard, but previously paid fees will not be subject to refund.</p>
    <p>9. Liability Waiver and Assumption of Risk</p>
    <p>The Member understands and expressly acknowledges that the use of tools, machinery, and materials within a makerspace environment involves inherent and substantial risks, including the potential for property damage, personal injury, burns, cuts, and even death.</p>
    <p>The Member hereby voluntarily assumes all risks associated with their presence and participation in Protohaven activities. To the fullest extent permitted by law, the Member agrees to release, indemnify, and hold harmless Protohaven, its employees, officers, and volunteers from any and all liability for injuries, damages, or losses arising from participation in Protohaven activities, except in cases of gross negligence or willful misconduct on the part of Protohaven.</p>
    <p>10. Indemnification</p>
    <p>The Member agrees to indemnify, defend, and hold harmless Protohaven and its personnel from and against any claims, liabilities, damages, or expenses (including reasonable attorney's fees) arising out of or related to:</p>
    <p>The Member's actions or omissions;</p>
    <p>The Member's violation of any provision of this Agreement; or</p>
    <p>Any damage caused by the Member to Protohaven's equipment or facilities.</p>
    <p>11. Governing Law and Amendments</p>
    <p>This Agreement shall be construed and governed in accordance with the laws of the Commonwealth of Pennsylvania, without regard to its conflict of law principles. Protohaven reserves the right to update its policies and the terms of this Agreement. The Member will be notified of any significant changes, and the Member's continued use of the Protohaven facility following notification constitutes binding acceptance of the updated terms.</p>
    <p>12. Acknowledgment and Signature</p>
    <p>By clicking the button below, the Member attests that they have thoroughly read, fully understand, and unconditionally agree to abide by all provisions of this Protohaven Member Agreement, including the Liability Waiver and Assumption of Risk outlined in Section 9.</p>
	</Card>

	<Row>
      <strong class="text-center">THIS IS A LEGAL AGREEMENT<br/>READ IT CAREFULLY AND BE CERTAIN YOU UNDERSTAND BEFORE SIGNING</strong>
		<Col class="d-flex justify-content-center py-3">
      <Button sm={{ size: 'auto'}} color='primary' on:click={on_submit} disabled={checking}>
        I have read and understand this agreement and agree to be bound by its requirements.</Button>
      {#if checking}
        <Spinner type="border" color="primary" class="mx-3" />
      {/if}
		</Col>
	</Row>
</Card>
