'use client';

import React from 'react';
import { BarVisualizer, useAgent, useSessionContext } from '@livekit/components-react';
import { motion, type MotionProps } from 'motion/react';
import { cn } from '@/lib/utils';

import { AgentAudioVisualizerAura } from '@/components/agents-ui/agent-audio-visualizer-aura';
import { AgentAudioVisualizerGrid } from '@/components/agents-ui/agent-audio-visualizer-grid';
import { AgentAudioVisualizerRadial } from '@/components/agents-ui/agent-audio-visualizer-radial';
import { AgentAudioVisualizerWave } from '@/components/agents-ui/agent-audio-visualizer-wave';

const MotionAgentAudioVisualizerAura = motion.create(AgentAudioVisualizerAura);
const MotionAgentAudioVisualizerGrid = motion.create(AgentAudioVisualizerGrid);
const MotionAgentAudioVisualizerRadial = motion.create(AgentAudioVisualizerRadial);
const MotionAgentAudioVisualizerWave = motion.create(AgentAudioVisualizerWave);

interface AudioVisualizerProps extends MotionProps {
  isChatOpen: boolean;
  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  audioVisualizerColor?: `#${string}`;
  audioVisualizerColorShift?: number;
  audioVisualizerWaveLineWidth?: number;
  audioVisualizerGridRowCount?: number;
  audioVisualizerGridColumnCount?: number;
  audioVisualizerRadialBarCount?: number;
  audioVisualizerRadialRadius?: number;
  audioVisualizerBarCount?: number;
  className?: string;
}

export function AudioVisualizer({
  audioVisualizerType = 'bar',
  audioVisualizerColor,
  audioVisualizerColorShift = 0.3,
  audioVisualizerBarCount = 5,
  audioVisualizerRadialRadius = 100,
  audioVisualizerRadialBarCount = 25,
  audioVisualizerGridRowCount = 15,
  audioVisualizerGridColumnCount = 15,
  audioVisualizerWaveLineWidth = 3,
  isChatOpen,
  className,
  ...props
}: AudioVisualizerProps) {
  const session = useSessionContext();
  const { state, microphoneTrack: audioTrack } = useAgent(session);

  switch (audioVisualizerType) {
    case 'aura': {
      return (
        <MotionAgentAudioVisualizerAura
          state={state}
          audioTrack={audioTrack}
          color={audioVisualizerColor}
          colorShift={audioVisualizerColorShift}
          className={cn('size-[300px] md:size-[450px]', className)}
          {...props}
        />
      );
    }
    case 'wave': {
      return (
        <motion.div className={className} {...props}>
          <MotionAgentAudioVisualizerWave
            state={state}
            audioTrack={audioTrack}
            color={audioVisualizerColor}
            colorShift={audioVisualizerColorShift}
            lineWidth={isChatOpen ? audioVisualizerWaveLineWidth * 2 : audioVisualizerWaveLineWidth}
            className="size-[300px] md:size-[450px]"
          />
        </motion.div>
      );
    }
    case 'grid': {
      const totalCount = audioVisualizerGridRowCount * audioVisualizerGridColumnCount;

      let size: 'icon' | 'sm' | 'md' | 'lg' | 'xl' = 'sm';
      if (totalCount < 100) {
        size = 'xl';
      } else if (totalCount < 200) {
        size = 'lg';
      } else if (totalCount < 300) {
        size = 'md';
      }

      return (
        <MotionAgentAudioVisualizerGrid
          size={size}
          state={state}
          color={audioVisualizerColor}
          audioTrack={audioTrack}
          rowCount={audioVisualizerGridRowCount}
          columnCount={audioVisualizerGridColumnCount}
          radius={Math.round(
            Math.min(audioVisualizerGridRowCount, audioVisualizerGridColumnCount) / 4,
          )}
          className={cn('size-[350px] gap-0 p-8 *:place-self-center md:size-[450px]', className)}
          {...props}
        />
      );
    }
    case 'radial': {
      return (
        <motion.div className={className} {...props}>
          <MotionAgentAudioVisualizerRadial
            size="xl"
            state={state}
            color={audioVisualizerColor}
            audioTrack={audioTrack}
            radius={audioVisualizerRadialRadius}
            barCount={audioVisualizerRadialBarCount}
            className="size-[450px]"
          />
        </motion.div>
      );
    }
    default: {
      let size: 'icon' | 'sm' | 'md' | 'lg' | 'xl' = 'icon';
      let sizedClassName = cn('size-[300px] md:size-[450px]', className);

      if (audioVisualizerBarCount <= 5) {
        size = 'xl';
        sizedClassName = cn('size-[450px] items-center justify-center gap-5', className);
      } else if (audioVisualizerBarCount <= 10) {
        size = 'lg';
        sizedClassName = cn('size-[450px]', className);
      } else if (audioVisualizerBarCount <= 15) {
        size = 'md';
        sizedClassName = cn('size-[350px] md:size-[450px]', className);
      } else if (audioVisualizerBarCount <= 30) {
        size = 'sm';
        sizedClassName = cn('size-[300px] md:size-[450px]', className);
      }

      return (
        <motion.div className={sizedClassName} style={{ color: audioVisualizerColor }} {...props}>
          <BarVisualizer
            state={state}
            track={audioTrack}
            barCount={audioVisualizerBarCount}
            options={{ minHeight: size === 'xl' ? 14 : 20, maxHeight: 100 }}
            className="flex h-full items-center justify-center gap-5"
          >
            <span className="block w-[56px] rounded-[999px] bg-current/70 data-[lk-highlighted=true]:bg-current data-[lk-highlighted=false]:opacity-75 min-h-[52px] md:min-h-[64px]" />
          </BarVisualizer>
        </motion.div>
      );
    }
  }
}
