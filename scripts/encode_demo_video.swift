import AVFoundation
import AppKit
import CoreVideo

struct Frame: Decodable {
    let path: String
    let delay: Double
}

guard CommandLine.arguments.count == 3 else {
    fatalError("usage: encode_demo_video.swift frames.json output.mp4")
}

let manifestURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
let frames = try JSONDecoder().decode([Frame].self, from: Data(contentsOf: manifestURL))
guard !frames.isEmpty else { fatalError("no frames to encode") }
let outputWidth = 1000
let outputHeight = 854
let writer = try AVAssetWriter(outputURL: outputURL, fileType: .mp4)
let input = AVAssetWriterInput(mediaType: .video, outputSettings: [
    AVVideoCodecKey: AVVideoCodecType.h264,
    AVVideoWidthKey: outputWidth,
    AVVideoHeightKey: outputHeight,
    AVVideoCompressionPropertiesKey: [
        AVVideoAverageBitRateKey: 1_800_000,
        AVVideoExpectedSourceFrameRateKey: 15,
        AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
    ],
])
input.expectsMediaDataInRealTime = false
let adaptor = AVAssetWriterInputPixelBufferAdaptor(
    assetWriterInput: input,
    sourcePixelBufferAttributes: [
        kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
        kCVPixelBufferWidthKey as String: outputWidth,
        kCVPixelBufferHeightKey as String: outputHeight,
        kCVPixelBufferCGImageCompatibilityKey as String: true,
        kCVPixelBufferCGBitmapContextCompatibilityKey as String: true,
    ]
)
guard writer.canAdd(input) else { fatalError("could not configure MP4 writer") }
writer.add(input)
guard writer.startWriting() else { throw writer.error ?? NSError(domain: "NightjarVideo", code: 1) }
writer.startSession(atSourceTime: .zero)

func resizedImage(from path: String) throws -> CGImage {
    guard let bitmap = NSImage(contentsOfFile: path) else {
        throw NSError(domain: "NightjarVideo", code: 2, userInfo: [NSLocalizedDescriptionKey: "could not open \(path)"])
    }
    var proposedRect = CGRect(origin: .zero, size: bitmap.size)
    guard let image = bitmap.cgImage(forProposedRect: &proposedRect, context: nil, hints: nil),
          let context = CGContext(
            data: nil,
            width: outputWidth,
            height: outputHeight,
            bitsPerComponent: 8,
            bytesPerRow: 0,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.noneSkipFirst.rawValue
          ) else {
        throw NSError(domain: "NightjarVideo", code: 3, userInfo: [NSLocalizedDescriptionKey: "could not rasterize \(path)"])
    }
    context.interpolationQuality = .high
    context.draw(image, in: CGRect(x: 0, y: 0, width: outputWidth, height: outputHeight))
    guard let resized = context.makeImage() else {
        throw NSError(domain: "NightjarVideo", code: 4, userInfo: [NSLocalizedDescriptionKey: "could not resize \(path)"])
    }
    return resized
}

var presentationTime = CMTime.zero
for frame in frames {
    try autoreleasepool {
        while !input.isReadyForMoreMediaData { Thread.sleep(forTimeInterval: 0.005) }
        var optionalBuffer: CVPixelBuffer?
        guard CVPixelBufferPoolCreatePixelBuffer(kCFAllocatorDefault, adaptor.pixelBufferPool!, &optionalBuffer) == kCVReturnSuccess,
              let buffer = optionalBuffer,
              CVPixelBufferLockBaseAddress(buffer, []) == kCVReturnSuccess,
              let context = CGContext(
                data: CVPixelBufferGetBaseAddress(buffer),
                width: outputWidth,
                height: outputHeight,
                bitsPerComponent: 8,
                bytesPerRow: CVPixelBufferGetBytesPerRow(buffer),
                space: CGColorSpaceCreateDeviceRGB(),
                bitmapInfo: CGBitmapInfo.byteOrder32Little.rawValue | CGImageAlphaInfo.premultipliedFirst.rawValue
              ) else { fatalError("could not allocate video frame") }
        context.draw(try resizedImage(from: frame.path), in: CGRect(x: 0, y: 0, width: outputWidth, height: outputHeight))
        CVPixelBufferUnlockBaseAddress(buffer, [])
        guard adaptor.append(buffer, withPresentationTime: presentationTime) else {
            throw writer.error ?? NSError(domain: "NightjarVideo", code: 5, userInfo: [NSLocalizedDescriptionKey: "could not append video frame"])
        }
        presentationTime = CMTimeAdd(presentationTime, CMTime(seconds: frame.delay, preferredTimescale: 600))
    }
}

input.markAsFinished()
let finished = DispatchSemaphore(value: 0)
writer.finishWriting { finished.signal() }
finished.wait()
guard writer.status == .completed else { throw writer.error ?? NSError(domain: "NightjarVideo", code: 6) }
