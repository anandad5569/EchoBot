class PCMRecorderProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.chunkSize = 2048;
        this.pending = new Float32Array(0);
    }

    process(inputs) {
        const input = inputs[0];
        if (!input || !input[0] || input[0].length === 0) {
            return true;
        }

        this.pending = mergeChunks(this.pending, input[0]);
        while (this.pending.length >= this.chunkSize) {
            const chunk = this.pending.slice(0, this.chunkSize);
            this.pending = this.pending.slice(this.chunkSize);
            this.port.postMessage(chunk, [chunk.buffer]);
        }
        return true;
    }
}

function mergeChunks(leftChunk, rightChunk) {
    if (!leftChunk || leftChunk.length === 0) {
        return new Float32Array(rightChunk);
    }

    const merged = new Float32Array(leftChunk.length + rightChunk.length);
    merged.set(leftChunk, 0);
    merged.set(rightChunk, leftChunk.length);
    return merged;
}

registerProcessor("pcm-recorder-processor", PCMRecorderProcessor);
