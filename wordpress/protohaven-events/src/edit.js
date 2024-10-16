/**
 * Retrieves the translation of text.
 *
 * @see https://developer.wordpress.org/block-editor/reference-guides/packages/packages-i18n/
 */

import { useBlockProps, InspectorControls } from '@wordpress/block-editor';
import { useEffect, useState } from '@wordpress/element';
import { TextControl, PanelBody } from '@wordpress/components';

import './style.scss';
import './editor.scss';
//import { get_events } from './lib';

/**
 * The edit function describes the structure of your block in the context of the
 * editor. This represents what the editor will render when the block is used.
 *
 * @see https://developer.wordpress.org/block-editor/reference-guides/block-api/block-edit-save/#edit
 *
 * @return {Element} Element to render.
 */
export default function Edit( { attributes, setAttributes } ) {
	const [state, setState] = useState([]);
	const { token } = attributes;
	useEffect(() => {
		//get_events(token).then(setState);
	}, []);

	function mkTextControl(attr_name, label) {
		return <TextControl __nextHasNoMarginBottom label={label} value={attributes[attr_name]} onChange={ (v) => {
			let update = {};
			update[attr_name] = v;
			return setAttributes(update);
		}}/>;
	}

	return (
		<>
			<InspectorControls>
				<PanelBody title={'Plugin Details'}>
					<div>See <a href="https://github.com/protohaven/protohaven_api/tree/main/wordpress/protohaven-events" target="_blank">protohaven_api github repository</a> for source code.</div>
				</PanelBody>
				<PanelBody title={'Neon Settings'}>{[
					mkTextControl('token', 'Access Token'),
				]}
				</PanelBody>
				<PanelBody title={'Render Settings'}>{[
					mkTextControl('imgSize', 'Image Width'),
				]}
				</PanelBody>
			</InspectorControls>
		<p { ...useBlockProps() } id="protohaven-events">
			<div>Event search page - rendered when viewing page. See https://github.com/protohaven/protohaven_api/tree/main/wordpress/protohaven-events for plugin source code.</div>
			<div>Requires a user token configured in Settings > Protohaven Events on the left sidebar of the Wordpress admin page</div>
		</p>
		</>
	);
}
