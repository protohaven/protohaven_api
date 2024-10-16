/**
 * Retrieves the translation of text.
 *
 * @see https://developer.wordpress.org/block-editor/reference-guides/packages/packages-i18n/
 */

import { useBlockProps, InspectorControls } from '@wordpress/block-editor';
import { RangeControl, TextControl, PanelBody } from '@wordpress/components';

import './style.scss';
import './editor.scss';
import { get_ph_data, render_grid } from './lib';

/**
 * The edit function describes the structure of your block in the context of the
 * editor. This represents what the editor will render when the block is used.
 *
 * @see https://developer.wordpress.org/block-editor/reference-guides/block-api/block-edit-save/#edit
 *
 * @return {Element} Element to render.
 */
export default function Edit( { attributes, setAttributes } ) {
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
					<div>See <a href="https://github.com/protohaven/protohaven_api/tree/main/wordpress/protohaven-airtable-grid" target="_blank">protohaven_api github repository</a> for source code.</div>
				</PanelBody>
				<PanelBody title={'Airtable Settings'}>{[
					mkTextControl('token', 'Access Token'),
					mkTextControl('base', 'Base ID'),
					mkTextControl('table', 'Table ID'),
				]}
				</PanelBody>
				<PanelBody title={'Field Settings'}>{[
					mkTextControl('titleField', 'Title Field'),
					mkTextControl('subtitleField', 'Subtitle Field'),
					mkTextControl('imgField', 'Image Field'),
					mkTextControl('bodyField', 'Body Field'),
					mkTextControl('refField', 'Link Field'),
				]}
				</PanelBody>
				<PanelBody title={'Render Settings'}>{[
					mkTextControl('imgSize', 'Image Width'),
					mkTextControl('refText', 'Link Display Text'),
				]}
				</PanelBody>
			</InspectorControls>
		<p { ...useBlockProps() } id="protohaven-airtable-grid">
			Table visible on page view - see https://github.com/protohaven/protohaven_api/tree/main/wordpress/protohaven-airtable-grid for plugin source
		</p>
		</>
	);
}
