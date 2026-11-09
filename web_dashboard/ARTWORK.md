# Transparent dashboard artwork

Updated 8 November 2026 using the built-in image generation/editing tool. Original assets are retained. The dashboard consumes:

- `public/assets/optibelt-logo-transparent.png`
- `public/assets/conveyor-transparent.png`

Both files contain transparent alpha rather than a painted background. The sidebar logo uses a light CSS rendition in dark mode. Conveyor lines are inverted with a hue correction in dark mode, preserving green accents; its container is transparent. The stopped-motor grayscale effect composes with the theme treatment.

Editing prompts:

**Logo:** Edit target: the supplied existing OPTIBELT logo. Background extraction only. Remove the pale gray rectangular background completely to true transparent alpha. Preserve the exact waveform mark, exact bold uppercase OPTIBELT lettering, proportions, arrangement and original dark charcoal ink. Do not redesign or retype into another style. Tight wide horizontal composition with small transparent padding, matching original aspect ratio. No shadows, no gradients, no background, no checkerboard painted into pixels. This is a production dashboard logo asset.

**Conveyor:** Edit target: supplied approved 2D technical conveyor drawing. Background extraction only. Remove the white paper background to genuine transparent alpha, including white negative spaces within the technical linework, around the drawing and around its labels. Preserve exact geometry and composition: green motor at lower left, coupling and geared drive, inclined conveyor up to right head pulley, legs, stockpile, belt green dashes and all existing text labels including Conveyor drive, Side elevation, Motor, Geared drive, Head pulley, Stockpile. Keep technical lines and text dark charcoal and preserve pale green motor fill. No redesign, no new elements, no 3D, no added shadows. Wide landscape same aspect ratio and proportions. Transparent background, not painted checkerboard. Intended as an overlay on a dashboard surface.

Verification: TypeScript/Vite production build; browser alpha inspection; light/dark screenshots; stopped-motor grayscale composition; no browser runtime errors. Screenshots and alpha measurements are in `verification/artwork*`. These are presentation changes only.
