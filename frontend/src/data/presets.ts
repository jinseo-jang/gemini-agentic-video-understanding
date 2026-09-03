import { VideoPreset } from '../types';

export const DEFAULT_PRESETS: VideoPreset[] = [
  {
    id: 'pixel-bts-5m',
    title: 'Google Pixel Production (5-Min Video)',
    subtitle: 'Behind the scenes long-form video demonstrating agentic scaling',
    size_mb: 37.69,
    mime_type: 'video/mp4',
    duration_seconds: 322.87,
    video_url: '/api/preset/video?preset_id=pixel-bts-5m',
    filename_display: 'Google Pixel Production [5-Min Video] 37.69 MB',
    default_prompt: 'Describe the different cameras, equipment, and filming setups used throughout this shoot, and what the director explains about filming on Pixel.'
  },
  {
    id: 'sustainability-4m',
    title: 'Google Sustainability (4-Min Keynote)',
    subtitle: 'Clean energy & data center sustainability presentation',
    size_mb: 33.81,
    mime_type: 'video/mp4',
    duration_seconds: 238.03,
    video_url: '/api/preset/video?preset_id=sustainability-4m',
    filename_display: 'Google Sustainability [4-Min Keynote] 33.81 MB',
    default_prompt: 'What specific clean energy targets and data center sustainability goals are presented in this video?'
  },
  {
    id: 'sports-10m',
    title: 'La Liga Football Match (10-Min Video)',
    subtitle: '10-minute sports broadcast demonstrating long-form frame retrieval',
    size_mb: 27.26,
    mime_type: 'video/mp4',
    duration_seconds: 600.0,
    video_url: '/api/preset/video?preset_id=sports-10m',
    filename_display: 'La Liga Football Match [10-Min Video] 27.26 MB',
    default_prompt: 'What match is this video showing, which teams are playing, and at what timestamps are goals or major shots attempted?'
  },
  {
    id: 'blog-demo-58s',
    title: 'DeepMind Needle Demo (58s Clip)',
    subtitle: 'Gemini 3.7 Flash Needle-in-a-Haystack benchmark demo',
    size_mb: 25.90,
    mime_type: 'video/mp4',
    duration_seconds: 58.67,
    video_url: '/api/preset/video?preset_id=blog-demo-58s',
    filename_display: 'DeepMind Needle Demo [58s Clip] 25.90 MB',
    default_prompt: 'In the OS terminal demo, what is the utility being used to display the locomotive?'
  }
];

export const PROMPT_SUGGESTIONS: { [key: string]: string[] } = {
  'pixel-bts-5m': [
    'Describe the different cameras, equipment, and filming setups used throughout this shoot, and what the director explains about filming on Pixel.',
    'At what points in the video is low-light or night filming discussed or shown?',
    'Summarize the key takeaways about using Pixel for professional video production.'
  ],
  'sustainability-4m': [
    'What specific clean energy targets and data center sustainability goals are presented in this video?',
    'How does Google plan to achieve 24/7 carbon-free energy across all its operations?',
    'What role does artificial intelligence play in optimizing data center energy efficiency?'
  ],
  'sports-10m': [
    'At what timestamp does Gareth Bale score the opening goal, and describe the goal?',
    'What match is this video showing, which teams are playing, and at what timestamps are goals or major shots attempted?',
    'Identify the players who scored goals in this match and specify their shirt numbers and approximate timestamps.',
    'Summarize the key events and momentum shifts across the 10 minutes of play.'
  ],
  'blog-demo-58s': [
    'In the OS terminal demo, what is the utility being used to display the locomotive?',
    'What command was typed into the terminal before the animated train appeared?',
    'Summarize the core message of this needle-in-a-haystack presentation clip.'
  ]
};
