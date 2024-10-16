/**
 * Retrieves the translation of text.
 *
 * @see https://developer.wordpress.org/block-editor/reference-guides/packages/packages-i18n/
 */

import { useBlockProps, InspectorControls } from '@wordpress/block-editor';
import { useEffect, useState } from '@wordpress/element';
import { SelectControl, PanelBody } from '@wordpress/components';

import './style.scss';
import './editor.scss';
import {ph_events_to_elems} from './lib';

function get_test_ph_events() {
	return new Promise((resolve, reject) => resolve([
		{
			"date": "Oct 15, 6PM",
			"name": "Textiles 102: CNC Testing Clearance",
			"seats_left": 4,
			"url": "https://protohaven.org/e/17881"
		},
		{
			"date": "Oct 18, 6PM",
			"name": "Wood 102: Test Clearance",
			"seats_left": 2,
			"url": "https://protohaven.org/e/17880"
		},
		{
			"date": "Oct 18, 6PM",
			"name": "Graphics 110: Vinyl Cut Signs (Vinyl Cutter Clearance)",
			"seats_left": 1,
			"url": "https://protohaven.org/e/17882"
		},
	]));
}

/**
 * The edit function describes the structure of your block in the context of the
 * editor. This represents what the editor will render when the block is used.
 *
 * @see https://developer.wordpress.org/block-editor/reference-guides/block-api/block-edit-save/#edit
 *
 * @return {Element} Element to render.
 */
export default function Edit( { attributes, setAttributes } ) {
	const { maxClassesShown } = attributes;
	const [state, setState] = useState([]);
	useEffect(() => {
		get_test_ph_events(maxClassesShown).then((events) => {
			events.splice(maxClassesShown);
			setState(events);
		});
	}, [maxClassesShown]);
	return (
		<>
			<InspectorControls>
				<PanelBody title={'Plugin Details'}>
					<div>See <a href="https://github.com/protohaven/protohaven_api/tree/main/wordpress/protohaven-class-ticker" target="_blank">protohaven_api github repository</a> for source code.</div>
				</PanelBody>
				<PanelBody title={'Settings'}>
					<SelectControl
						__nextHasNoMarginBottom
						label="Max Classes Shown"
						value={ maxClassesShown }
						options={ [
							{ value: 1, label: '1' },
							{ value: 2, label: '2' },
							{ value: 3, label: '3' },
						] }
						onChange={ (v) => setAttributes({maxClassesShown: v}) }
					/>
				</PanelBody>
			</InspectorControls>
		<p { ...useBlockProps() } id="protohaven-class-ticker">
			{ ph_events_to_elems(state) }
		</p>
		</>
	);
}
