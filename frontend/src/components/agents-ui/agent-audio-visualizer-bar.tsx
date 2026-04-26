'use client';

import React, {
  type CSSProperties,
  Children,
  type ComponentProps,
  type ReactNode,
  cloneElement,
  isValidElement,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { type VariantProps, cva } from 'class-variance-authority';
import { type LocalAudioTrack, type RemoteAudioTrack } from 'livekit-client';
import {
  type AgentState,
  type TrackReferenceOrPlaceholder,
  useMultibandTrackVolume,
} from '@livekit/components-react';
import { useAgentAudioVisualizerBarAnimator } from '@/hooks/agents-ui/use-agent-audio-visualizer-bar';
import { cn } from '@/lib/utils';

function cloneSingleChild(
  children: ReactNode | ReactNode[],
  props?: Record<string, unknown>,
  key?: unknown,
) {
  return Children.map(children, (child) => {
    // Checking isValidElement is the safe way and avoids a typescript error too.
    if (isValidElement(child) && Children.only(children)) {
      const childProps = child.props as Record<string, unknown>;
      if (childProps.className) {
        // make sure we retain classnames of both passed props and child
        props ??= {};
        props.className = cn(childProps.className as string, props.className as string);
        props.style = {
          ...(childProps.style as CSSProperties),
          ...(props.style as CSSProperties),
        };
      }
      return cloneElement(child, { ...props, key: key ? String(key) : undefined });
    }
    return child;
  });
}

export const AgentAudioVisualizerBarElementVariants = cva(
  [
    'rounded-full transition-colors duration-250 ease-linear',
    'bg-current/70 data-[lk-highlighted=true]:bg-current data-[lk-highlighted=false]:opacity-75',
  ],
  {
    variants: {
      size: {
        icon: 'w-[4px] min-h-[4px]',
        sm: 'w-[8px] min-h-[8px]',
        md: 'w-[16px] min-h-[16px]',
        lg: 'w-[32px] min-h-[32px]',
        xl: 'w-[56px] min-h-[52px] md:min-h-[64px]',
      },
    },
    defaultVariants: {
      size: 'md',
    },
  },
);

export const AgentAudioVisualizerBarVariants = cva('relative flex items-center justify-center', {
  variants: {
    size: {
      icon: 'h-[24px] gap-[2px]',
      sm: 'h-[56px] gap-[4px]',
      md: 'h-[112px] gap-[8px]',
      lg: 'h-[224px] gap-[16px]',
      xl: 'h-[448px] gap-[20px]',
    },
  },
  defaultVariants: {
    size: 'md',
  },
});

/**
 * Props for the AgentAudioVisualizerBar component.
 */
export interface AgentAudioVisualizerBarProps {
  /**
   * The size of the visualizer.
   * @defaultValue 'md'
   */
  size?: 'icon' | 'sm' | 'md' | 'lg' | 'xl';
  /**
   * The current state of the agent. Determines the animation pattern.
   * @defaultValue 'connecting'
   */
  state?: AgentState;
  /**
   * The color of the bars in hexidecimal format.
   */
  color?: `#${string}`;
  /**
   * The number of bars to display in the visualizer.
   * If not provided, defaults based on size: 3 for 'icon'/'sm', 5 for others.
   */
  barCount?: number;
  /**
   * The audio track to visualize. Can be a local/remote audio track or a track reference.
   */
  audioTrack?: LocalAudioTrack | RemoteAudioTrack | TrackReferenceOrPlaceholder;
  /**
   * Additional CSS class names to apply to the container.
   */
  className?: string;
  /**
   * Custom div element to render as grid cells. Each child receives data-lk-index,
   * data-lk-highlighted props and style props for height. Must be a single div element.
   */
  children?: ReactNode;
}

/**
 * A bar-style audio visualizer that responds to agent state and audio levels.
 * Displays animated bars that react to the current agent state (connecting, thinking, speaking, etc.)
 * and audio volume when speaking.
 *
 * @extends ComponentProps<'div'>
 *
 * @example
 * ```tsx
 * <AgentAudioVisualizerBar
 *   size="md"
 *   state="speaking"
 *   audioTrack={agentAudioTrack}
 * />
 * ```
 */
export function AgentAudioVisualizerBar({
  size = 'md',
  state = 'connecting',
  color,
  barCount,
  audioTrack,
  className,
  children,
  style,
  ...props
}: AgentAudioVisualizerBarProps &
  VariantProps<typeof AgentAudioVisualizerBarVariants> &
  ComponentProps<'div'>) {
  const [animationTick, setAnimationTick] = useState(0);
  const isActiveState =
    state === 'speaking' ||
    state === 'thinking' ||
    state === 'listening' ||
    state === 'idle' ||
    state === 'initializing' ||
    state === 'pre-connect-buffering';

  const _barCount = useMemo(() => {
    if (barCount) {
      return barCount;
    }
    switch (size) {
      case 'icon':
      case 'sm':
        return 3;
      default:
        return 5;
    }
  }, [barCount, size]);

  const volumeBands = useMultibandTrackVolume(audioTrack, {
    bands: _barCount,
    loPass: 100,
    hiPass: 200,
  });

  const sequencerInterval = useMemo(() => {
    switch (state) {
      case 'connecting':
        return 2000 / _barCount;
      case 'initializing':
        return 2000;
      case 'listening':
        return 500;
      case 'thinking':
        return 150;
      default:
        return 1000;
    }
  }, [state, _barCount]);

  const highlightedIndices = useAgentAudioVisualizerBarAnimator(
    state,
    _barCount,
    sequencerInterval,
  );

  useEffect(() => {
    if (!isActiveState) {
      return;
    }

    const intervalId = window.setInterval(() => {
      setAnimationTick((current) => current + 1);
    }, state === 'speaking' ? 120 : state === 'thinking' ? 180 : 240);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [isActiveState, state]);

  const bands = useMemo(() => {
    const isInactive = state === 'disconnected' || state === 'failed' || state === 'connecting';
    const hasSignal = volumeBands.some((band) => band > 0.01);
    const idlePattern = [0.82, 0.68, 0.72, 0.5, 0.86];
    const speakingPattern = [0.88, 0.56, 0.78, 0.52, 0.92];
    const connectedPattern = [0.62, 0.44, 0.58, 0.4, 0.66];

    if (isInactive && !hasSignal) {
      return new Array(_barCount).fill(0);
    }

    if (!hasSignal && state === 'speaking') {
      return new Array(_barCount).fill(0).map((_, idx) => {
        const phase = animationTick * 0.85 + idx * 0.9;
        const wave = (Math.sin(phase) + 1) / 2;
        const base = speakingPattern[idx % speakingPattern.length] * 0.38;

        return Math.min(1, base + wave * 0.42);
      });
    }

    if (!hasSignal && state === 'thinking') {
      return new Array(_barCount).fill(0).map((_, idx) => {
        const phase = animationTick * 0.5 + idx * 0.65;
        const wave = (Math.sin(phase) + 1) / 2;
        return 0.18 + wave * 0.16;
      });
    }

    if (!hasSignal) {
      return new Array(_barCount).fill(0).map((_, idx) => {
        const phase = animationTick * 0.35 + idx * 0.75;
        const wave = (Math.sin(phase) + 1) / 2;
        const base = connectedPattern[idx % connectedPattern.length] * 0.24;

        return Math.min(0.42, base + wave * 0.14);
      });
    }

    return new Array(_barCount).fill(0).map((_, idx) => {
      const band = volumeBands[idx] ?? 0;
      const fallback = idlePattern[idx % idlePattern.length] * 0.2;

      if (!hasSignal) {
        return fallback;
      }

      return Math.max(fallback, Math.min(1, band * 1.6 + fallback));
    });
  }, [animationTick, state, volumeBands, _barCount]);

  if (children && Array.isArray(children)) {
    throw new Error('AgentAudioVisualizerBar children must be a single element.');
  }

  return (
    <div
      data-lk-state={state}
      style={{ ...style, color } as CSSProperties}
      className={cn(AgentAudioVisualizerBarVariants({ size }), className)}
      {...props}
    >
      {bands.map((band: number, idx: number) =>
        children ? (
          <React.Fragment key={idx}>
            {cloneSingleChild(children, {
              'data-lk-index': idx,
              'data-lk-highlighted': highlightedIndices.includes(idx),
              style: { height: `${band * 100}%` },
            })}
          </React.Fragment>
        ) : (
          <div
            key={idx}
            data-lk-index={idx}
            data-lk-highlighted={highlightedIndices.includes(idx)}
            style={{ height: `${band * 100}%` }}
            className={cn(AgentAudioVisualizerBarElementVariants({ size }))}
          />
        ),
      )}
    </div>
  );
}
