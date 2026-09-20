import { Injectable } from '@angular/core';
import { driver, Driver, DriveStep } from 'driver.js';

// Events emitted by the app while the user works through the tour.
// Each interactive step waits for one of these before it advances.
export type TourEvent =
  | 'from-selected'
  | 'to-selected'
  | 'routes-displayed'
  | 'metrics-opened';

interface TourStep {
  // [data-tour] key of the element to spotlight; undefined -> centered popover
  target?: string;
  title: string;
  description: string;
  side?: 'left' | 'right' | 'top' | 'bottom';
  // Where the target lives; decides how the layout is prepared on mobile.
  area?: 'controls' | 'map';
  // If set the step has no "Next" button and advances only when the event matches.
  waitFor?: (event: TourEvent, payload?: any) => boolean;
  // Skip the step when the app is already in the state it would ask for.
  skipIf?: () => boolean;
  // Runs right before the step is shown (open panels, scroll, ...).
  before?: () => void;
}

// Minimal view of the controls component the tour needs; avoids a circular import.
export interface TourHost {
  hasFrom(): boolean;
  hasTo(): boolean;
  isModeActive(mode: string): boolean;
  isRouteDisplayed(mode: string): boolean;
  isMetricsOpen(): boolean;
  isMobile(): boolean;
  showControls(): void;
  hideControls(): void;
  selectChart(chart: 'altitude' | 'green' | 'noise' | 'air'): void;
}

// localStorage key remembering that the user finished or declined the tour
const STORAGE_KEY = 'routify.tour';

@Injectable({ providedIn: 'root' })
export class TourService {
  private driver: Driver | null = null;
  private host: TourHost | null = null;
  private steps: TourStep[] = [];
  private current = -1;

  public isActive(): boolean {
    return this.driver?.isActive() ?? false;
  }

  // True until the user has either completed or declined the tour once.
  public shouldOffer(): boolean {
    try {
      return localStorage.getItem(STORAGE_KEY) === null;
    } catch {
      return false;
    }
  }

  private remember(value: 'done' | 'dismissed'): void {
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // storage unavailable (private mode etc.) -> simply ask again next time
    }
  }

  // Shows a small "want a tour?" prompt; starts the tour on yes, remembers the choice on no.
  public offer(host: TourHost): void {
    if (this.isActive()) return;
    const prompt = driver({
      animate: true,
      overlayOpacity: 0.4,
      allowClose: true,
      popoverClass: 'routify-tour-popover',
      onDestroyed: () => {
        document.body.classList.remove('routify-tour-active');
        if (!accepted) this.remember('dismissed');
      },
    });
    let accepted = false;
    document.body.classList.add('routify-tour-active');
    prompt.highlight({
      popover: {
        title: 'New to Routify?',
        description:
          'Take a short guided tour: enter an address, compute the shortest route, add a green alternative and compare them in the chart. ' +
          'You can restart it anytime via the <b>Take a tour</b> button. ' +
          'Your choice is remembered in this browser only (no cookies, no tracking).',
        showButtons: ['next', 'close'],
        nextBtnText: 'Start tour',
        onNextClick: () => {
          accepted = true;
          prompt.destroy();
          this.start(host);
        },
        onPopoverRender: (popover) => {
          const noThanks = document.createElement('button');
          noThanks.innerText = 'No thanks';
          noThanks.className = 'routify-tour-decline-btn';
          noThanks.onclick = () => prompt.destroy();
          popover.footerButtons.prepend(noThanks);
        },
      },
    });
  }

  public start(host: TourHost): void {
    if (this.isActive()) this.driver?.destroy();
    this.host = host;
    this.steps = this.buildSteps(host);
    this.current = -1;

    this.driver = driver({
      animate: true,
      overlayOpacity: 0.6,
      stagePadding: 6,
      stageRadius: 8,
      allowClose: true,
      showProgress: true,
      progressText: '{{current}} of {{total}}',
      popoverClass: 'routify-tour-popover',
      steps: this.steps.map((step, i) => this.toDriveStep(step, i)),
      onDestroyed: () => {
        document.body.classList.remove('routify-tour-active');
        this.current = -1;
        // finished or closed early: either way don't offer it again automatically
        this.remember('done');
      },
    });

    document.body.classList.add('routify-tour-active');
    host.showControls();
    // Give the sidebar / bottom-bar transition a moment so the spotlight lands on the right spot.
    setTimeout(() => this.show(0), 350);
  }

  public stop(): void {
    this.driver?.destroy();
  }

  // Called by the app whenever something tour-relevant happens.
  public notify(event: TourEvent, payload?: any): void {
    if (!this.isActive()) return;
    const step = this.steps[this.current];
    if (step?.waitFor && step.waitFor(event, payload)) {
      // Let Angular paint the new state before moving the spotlight.
      setTimeout(() => this.show(this.current + 1), 250);
    }
  }

  private show(index: number): void {
    const drv = this.driver;
    if (!drv) return;
    // Skip steps whose precondition is already met.
    while (index < this.steps.length && this.steps[index].skipIf?.()) index++;
    if (index >= this.steps.length) {
      drv.destroy();
      return;
    }
    const step = this.steps[index];
    this.current = index;
    // On mobile the controls live in a collapsible bottom bar: open it for control
    // steps and collapse it for map steps so the spotlight is actually visible.
    if (this.host?.isMobile()) {
      if (step.area === 'controls') this.host.showControls();
      if (step.area === 'map') this.host.hideControls();
    }
    step.before?.();
    // `drive` initialises the overlay on the first call; afterwards `moveTo` keeps the state.
    const go = () => (drv.isActive() ? drv.moveTo(index) : drv.drive(index));
    // A short delay lets layout side effects (bar transition, expansion panels) render first.
    setTimeout(go, step.before || this.host?.isMobile() ? 400 : 0);
  }

  private toDriveStep(step: TourStep, index: number): DriveStep {
    const isLast = index === this.steps.length - 1;
    // Desktop: controls sit in the left sidebar, so popovers go right / left of the map.
    // Mobile: controls sit in the bottom bar, so popovers go above them / below the map top.
    const mobile = this.host?.isMobile() ?? false;
    const side = mobile ? (step.area === 'map' ? 'bottom' : 'top') : step.side ?? 'right';
    return {
      element: step.target ? () => this.resolve(step.target!) : undefined,
      popover: {
        title: step.title,
        description: step.description,
        side,
        align: mobile || step.side === 'left' ? 'center' : 'start',
        showButtons: step.waitFor ? ['close'] : ['next', 'close'],
        nextBtnText: isLast ? 'Finish' : 'Next',
        doneBtnText: 'Finish',
        onNextClick: () => (isLast ? this.driver?.destroy() : this.show(index + 1)),
      },
    };
  }

  // Both the desktop sidebar and the mobile bar render a controls component,
  // so pick the [data-tour] element that is actually visible.
  private resolve(key: string): Element {
    const candidates = Array.from(document.querySelectorAll<HTMLElement>(`[data-tour="${key}"]`));
    return candidates.find((el) => el.offsetParent !== null) ?? candidates[0] ?? document.body;
  }

  private buildSteps(host: TourHost): TourStep[] {
    const mobile = host.isMobile();
    return [
      {
        title: 'Welcome to Routify',
        description:
          'This short tour walks you from entering an address to comparing routes. ' +
          'Follow the highlighted element in each step.',
      },
      {
        target: 'address-from',
        area: 'controls',
        title: 'Starting point',
        description:
          'Type an address, e.g. <b>ETH Zürich</b>, and pick a suggestion from the list.',
        waitFor: (e) => e === 'from-selected',
        skipIf: () => host.hasFrom(),
      },
      {
        target: 'address-to',
        area: 'controls',
        title: 'Destination',
        description: 'Now enter where you want to go, e.g. <b>Zürich Stadelhofen</b>.',
        waitFor: (e) => e === 'to-selected',
        skipIf: () => host.hasTo(),
      },
      {
        target: 'transport-modes',
        area: 'controls',
        title: 'Transport mode',
        description:
          'Routes are calculated for walking by default. You can switch to cycling or driving at any time.',
      },
      {
        target: 'mode-distance',
        area: 'controls',
        title: 'Shortest route',
        description:
          'Click the signpost to compute the <b>shortest route</b> — this is the baseline every other route is compared against.',
        waitFor: (e, p) => e === 'routes-displayed' && p?.includes('routing_mode_distance'),
        skipIf: () => host.isRouteDisplayed('routing_mode_distance'),
      },
      {
        target: 'map',
        area: 'map',
        title: 'Your route on the map',
        description:
          'The shortest route is drawn on the map. Start and destination markers can be dragged to move the route.',
        side: 'left',
      },
      {
        target: 'mode-green',
        area: 'controls',
        title: 'Add a green route',
        description:
          'Click the leaf to add a route that prefers parks, trees and green spaces. ' +
          'Right-click the button later to adjust how strongly greenery is weighted.',
        waitFor: (e, p) => e === 'routes-displayed' && p?.includes('routing_mode_green'),
        skipIf: () => host.isRouteDisplayed('routing_mode_green'),
      },
      {
        target: 'map',
        area: 'map',
        title: 'Compare routes',
        description:
          'Both routes are now shown in their own colour. ' +
          (mobile ? 'Tap' : 'Hover') + ' a route to see details about that segment.',
        side: 'left',
      },
      {
        target: 'metrics-header',
        area: 'controls',
        title: 'Route insights',
        description: 'Open <b>Route insights</b> to compare the routes by their metrics.',
        waitFor: (e) => e === 'metrics-opened',
        skipIf: () => host.isMetricsOpen(),
      },
      {
        // the whole card (chart + explanations) is too tall for the mobile bar, so spotlight only the plot there
        target: mobile ? 'chart-plot' : 'chart',
        area: 'controls',
        title: 'Green index along the route',
        description:
          'The chart plots the selected metric over the length of each route. ' +
          (mobile ? 'Tapping' : 'Hovering') + ' a point in the chart highlights the same spot on the map.',
        before: () => host.selectChart('green'),
      },
      {
        target: 'chart-metrics',
        area: 'controls',
        title: 'Other metrics',
        description:
          'Switch between altitude, green index, noise and air pollution, or enable the overlay to see all of them at once. ' +
          'That is it — enjoy exploring!',
      },
    ];
  }
}
