var pc = null;

function getEl(id) {
    return document.getElementById(id);
}

function getStoredOrDefault(key, fallback) {
    try {
        const v = localStorage.getItem(key);
        return (v === null || v === undefined || v === '') ? fallback : v;
    } catch (e) {
        return fallback;
    }
}

function setStored(key, value) {
    try { localStorage.setItem(key, value); } catch (e) {}
}

function negotiate() {
    pc.addTransceiver('video', { direction: 'recvonly' });
    pc.addTransceiver('audio', { direction: 'recvonly' });
    return pc.createOffer().then((offer) => {
        return pc.setLocalDescription(offer);
    }).then(() => {
        // wait for ICE gathering to complete
        return new Promise((resolve) => {
            if (pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                const checkState = () => {
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                };
                pc.addEventListener('icegatheringstatechange', checkState);
            }
        });
    }).then(() => {
        var offer = pc.localDescription;
        return fetch('/offer', {
            body: JSON.stringify({
                sdp: offer.sdp,
                type: offer.type,
            }),
            headers: {
                'Content-Type': 'application/json'
            },
            method: 'POST'
        });
    }).then(async (response) => {
        const raw = await response.text();
        if (!response.ok) {
            throw new Error(`/offer failed (${response.status}): ${raw.slice(0, 400)}`);
        }
        try {
            return JSON.parse(raw);
        } catch (e) {
            throw new Error(`/offer returned non-JSON: ${raw.slice(0, 400)}`);
        }
    }).then((answer) => {
        if (answer && answer.code && answer.code !== 0) {
            throw new Error(answer.msg || 'offer error');
        }
        document.getElementById('sessionid').value = answer.sessionid
        return pc.setRemoteDescription(answer);
    }).catch((e) => {
        alert(e);
    });
}

function start() {
    var config = {
        sdpSemantics: 'unified-plan'
    };

    // 【Zegao】ICE servers: STUN (optional) + TURN (recommended for remote/campus networks)
    const iceServers = [];
    if (getEl('use-stun') && getEl('use-stun').checked) {
        iceServers.push({ urls: ['stun:stun.l.google.com:19302'] });
    }

    if (getEl('use-turn') && getEl('use-turn').checked) {
        const host = (getEl('turn-host') && getEl('turn-host').value.trim())
            ? getEl('turn-host').value.trim()
            : window.location.hostname;
        const username = (getEl('turn-user') && getEl('turn-user').value.trim()) ? getEl('turn-user').value.trim() : '';
        const credential = (getEl('turn-pass') && getEl('turn-pass').value.trim()) ? getEl('turn-pass').value.trim() : '';

        // Persist for convenience
        setStored('cityu_turn_host', host);
        setStored('cityu_turn_user', username);
        setStored('cityu_turn_pass', credential);

        // TURN over TCP 443: most firewall-friendly
        iceServers.push({
            urls: [`turn:${host}:443?transport=tcp`],
            username,
            credential
        });
    }

    if (iceServers.length > 0) {
        config.iceServers = iceServers;
    }

    pc = new RTCPeerConnection(config);

    // connect audio / video
    pc.addEventListener('track', (evt) => {
        if (evt.track.kind == 'video') {
            const videoElement = document.getElementById('video');
            document.getElementById('video').srcObject = evt.streams[0];
            videoElement.playbackRate = 2.0; // 2倍速播放

        } else {
            document.getElementById('audio').srcObject = evt.streams[0];
        }
    });

    document.getElementById('start').style.display = 'none';
    negotiate();
    document.getElementById('stop').style.display = 'inline-block';
}

function stop() {
    document.getElementById('stop').style.display = 'none';

    document.getElementById('start').style.display = 'inline-block';

    // close peer connection
    // setTimeout(() => {
    //     pc.close();
    // }, 500);

    // 关闭 WebRTC 连接
    setTimeout(() => {
        if (pc) {
            pc.close();
            pc = null; // 重置 pc 变量
        }
    }, 500);
}

window.onunload = function(event) {
    // 在这里执行你想要的操作
    setTimeout(() => {
        pc.close();
    }, 500);
};

window.onbeforeunload = function (e) {
        setTimeout(() => {
                pc.close();
            }, 500);
        e = e || window.event
        // 兼容IE8和Firefox 4之前的版本
        if (e) {
          e.returnValue = '关闭提示'
        }
        // Chrome, Safari, Firefox 4+, Opera 12+ , IE 9+
        return '关闭提示'
      }

// 【Zegao】Initialize TURN fields from localStorage (if present)
window.addEventListener('DOMContentLoaded', () => {
    const hostEl = getEl('turn-host');
    const userEl = getEl('turn-user');
    const passEl = getEl('turn-pass');
    if (hostEl) hostEl.value = getStoredOrDefault('cityu_turn_host', '');
    if (userEl) userEl.value = getStoredOrDefault('cityu_turn_user', '');
    if (passEl) passEl.value = getStoredOrDefault('cityu_turn_pass', '');
});