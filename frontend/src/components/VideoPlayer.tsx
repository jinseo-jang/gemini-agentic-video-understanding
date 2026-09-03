import React from 'react';
import { Film, AlertCircle } from 'lucide-react';
import { VideoSourceType } from '../types';

interface VideoPlayerProps {
  videoUrl: string;
  sourceType: VideoSourceType;
  title?: string;
  className?: string;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  videoUrl,
  sourceType,
  className = '',
}) => {
  // Helper to extract YouTube embed URL
  const getYouTubeEmbedUrl = (url: string): string | null => {
    try {
      if (url.includes('youtube.com/watch')) {
        const urlObj = new URL(url);
        const v = urlObj.searchParams.get('v');
        return v ? `https://www.youtube.com/embed/${v}` : null;
      }
      if (url.includes('youtu.be/')) {
        const id = url.split('youtu.be/')[1]?.split(/[?#]/)[0];
        return id ? `https://www.youtube.com/embed/${id}` : null;
      }
      if (url.includes('youtube.com/embed/')) {
        return url;
      }
    } catch {
      return null;
    }
    return null;
  };

  if (!videoUrl) {
    return (
      <div className={`aspect-video w-full border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/70 flex flex-col items-center justify-center text-slate-400 p-6 ${className}`}>
        <Film className="w-8 h-8 mb-2 stroke-[1.5] text-slate-300" />
        <span className="text-xs font-medium text-slate-400">drop video here</span>
        <span className="text-[11px] text-slate-400/80 mt-1">or select a preset keynote clip below</span>
      </div>
    );
  }

  // Check for YouTube
  if (sourceType === 'youtube' || videoUrl.includes('youtube.com') || videoUrl.includes('youtu.be')) {
    const embedUrl = getYouTubeEmbedUrl(videoUrl);
    if (!embedUrl) {
      return (
        <div className="aspect-video w-full bg-slate-900 rounded-xl flex flex-col items-center justify-center text-rose-400 p-4">
          <AlertCircle className="w-6 h-6 mb-1" />
          <span className="text-xs font-semibold">Invalid YouTube URL</span>
        </div>
      );
    }
    return (
      <div className={`relative aspect-video w-full rounded-xl overflow-hidden bg-black border border-slate-200/90 shadow-sm ${className}`}>
        <iframe
          src={embedUrl}
          title="YouTube video player"
          className="w-full h-full border-0"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
        />
      </div>
    );
  }

  // HTML5 MP4 / Direct stream
  return (
    <div className={`relative aspect-video w-full rounded-xl overflow-hidden bg-black border border-slate-200/90 shadow-sm ${className}`}>
      <video
        key={videoUrl}
        src={videoUrl}
        controls
        playsInline
        preload="metadata"
        className="w-full h-full object-contain"
      >
        Your browser does not support the video tag.
      </video>
    </div>
  );
};
