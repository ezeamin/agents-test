/**
 * WebRTC helpers — ICE server config and SDP offer/answer exchange for Pipecat SmallWebRTCTransport.
 *
 * Optional env variable:
 *   VITE_ICE_SERVERS  comma-separated STUN/TURN URLs
 *                     default: stun:stun.l.google.com:19302,stun:stun1.l.google.com:19302
 */

// Shape expected by PATCH /api/offer
interface IceCandidatePayload {
  pc_id: string;
  candidates: {
    candidate: string;
    sdp_mid: string | null;
    sdp_mline_index: number | null;
  }[];
}

// Shape returned by POST /api/offer
export interface AnswerPayload {
  sdp: string;
  type: RTCSdpType;
  pc_id: string;
}

export function buildIceServers(): RTCIceServer[] {
  const raw = import.meta.env.VITE_ICE_SERVERS as string | undefined;
  const urls = raw?.trim()
    ? raw.split(',').map((s) => s.trim())
    : ['stun:stun.l.google.com:19302', 'stun:stun1.l.google.com:19302'];
  return [{ urls }];
}

export function createPeerConnection(): RTCPeerConnection {
  return new RTCPeerConnection({ iceServers: buildIceServers() });
}

export async function sendIceCandidate(
  pcId: string,
  candidate: RTCIceCandidateInit,
): Promise<void> {
  const payload: IceCandidatePayload = {
    pc_id: pcId,
    candidates: [
      {
        candidate: candidate.candidate ?? '',
        sdp_mid: candidate.sdpMid ?? null,
        sdp_mline_index: candidate.sdpMLineIndex ?? null,
      },
    ],
  };

  await fetch('/api/offer', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function exchangeSdpOffer(
  pc: RTCPeerConnection,
): Promise<AnswerPayload> {
  const offer = pc.localDescription;
  if (!offer) throw new Error('No local description set');

  const res = await fetch('/api/offer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sdp: offer.sdp, type: offer.type }),
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`SDP offer failed: ${res.status} — ${detail}`);
  }

  return (await res.json()) as AnswerPayload;
}
