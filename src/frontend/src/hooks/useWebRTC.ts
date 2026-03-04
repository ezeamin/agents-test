import { useCallback, useRef, useState } from 'react';
import {
  createPeerConnection,
  exchangeSdpOffer,
  sendIceCandidate,
} from '@/lib/webrtc';
import type { ConnectionStatus } from '@/types';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface UseWebRTCReturn {
  connectionState: ConnectionStatus;
  isMuted: boolean;
  connect: () => Promise<void>;
  disconnect: () => void;
  toggleMute: () => void;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useWebRTC(): UseWebRTCReturn {
  const [connectionState, setConnectionState] =
    useState<ConnectionStatus>('disconnected');
  const [isMuted, setIsMuted] = useState(false);

  const pcRef = useRef<RTCPeerConnection | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioElRef = useRef<HTMLAudioElement | null>(null);

  // ── Cleanup ──────────────────────────────────────────────────────────────────
  function cleanup() {
    pcRef.current?.close();
    pcRef.current = null;

    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    if (audioElRef.current) {
      audioElRef.current.srcObject = null;
      audioElRef.current = null;
    }

    setIsMuted(false);
  }

  // ── Connect ─────────────────────────────────────────────────────────────────
  const connect = useCallback(async () => {
    if (pcRef.current) return; // already connecting / connected
    setConnectionState('connecting');

    try {
      // 1. Acquire microphone
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const audioTrack = stream.getAudioTracks()[0]!;

      // 2. Create peer connection
      const pc = createPeerConnection();
      pcRef.current = pc;

      // ICE candidate queue — hold candidates until we receive pc_id from the SDP answer
      const pendingCandidates: RTCIceCandidateInit[] = [];
      let pcId: string | null = null;
      let canFlush = false;

      pc.onicecandidate = async (evt) => {
        if (!evt.candidate) return;
        if (canFlush && pcId) {
          await sendIceCandidate(pcId, evt.candidate.toJSON());
        } else {
          pendingCandidates.push(evt.candidate.toJSON());
        }
      };

      pc.onconnectionstatechange = () => {
        const s = pc.connectionState;
        if (s === 'connected') {
          setConnectionState('connected');
        } else if (s === 'disconnected' || s === 'failed' || s === 'closed') {
          cleanup();
          setConnectionState('disconnected');
        }
      };

      // Play remote audio
      pc.ontrack = (evt) => {
        if (!audioElRef.current) {
          const el = new Audio();
          el.autoplay = true;
          audioElRef.current = el;
        }
        audioElRef.current.srcObject = evt.streams[0] ?? null;
      };

      // SmallWebRTCTransport requires BOTH audio and video transceivers
      pc.addTransceiver(audioTrack, { direction: 'sendrecv' });
      pc.addTransceiver('video', { direction: 'sendrecv' });

      // 3. SDP offer ↔ answer
      await pc.setLocalDescription(await pc.createOffer());
      const answer = await exchangeSdpOffer(pc);
      pcId = answer.pc_id;
      await pc.setRemoteDescription({ sdp: answer.sdp, type: answer.type });

      // 4. Flush queued ICE candidates
      canFlush = true;
      for (const c of pendingCandidates) {
        await sendIceCandidate(pcId, c);
      }
      pendingCandidates.length = 0;
    } catch (err) {
      console.error('[useWebRTC] connect failed', err);
      cleanup();
      setConnectionState('disconnected');
    }
  }, []);

  // ── Disconnect ───────────────────────────────────────────────────────────────
  const disconnect = useCallback(() => {
    cleanup();
    setConnectionState('disconnected');
  }, []);

  // ── Mute toggle ──────────────────────────────────────────────────────────────
  const toggleMute = useCallback(() => {
    const tracks = streamRef.current?.getAudioTracks();
    if (!tracks?.length) return;
    const nextEnabled = !tracks[0]!.enabled;
    tracks.forEach((t) => {
      t.enabled = nextEnabled;
    });
    setIsMuted(!nextEnabled);
  }, []);

  return { connectionState, isMuted, connect, disconnect, toggleMute };
}
