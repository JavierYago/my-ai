// Captura el audio del micrófono en bloques y se los pasa a la página para detectar la voz.
class RecorderProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(1024);
    this.length = 0;
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel) {
      for (let i = 0; i < channel.length; i++) {
        this.buffer[this.length++] = channel[i];
        if (this.length === this.buffer.length) {
          this.port.postMessage(this.buffer.slice());
          this.length = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor("recorder", RecorderProcessor);
