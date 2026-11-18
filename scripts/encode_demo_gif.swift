import Foundation
import AppKit
import ImageIO
import UniformTypeIdentifiers

struct Frame: Decodable {
    let path: String
    let delay: Double
}

guard CommandLine.arguments.count == 3 else {
    fatalError("usage: encode_demo_gif.swift frames.json output.gif")
}

let manifestURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
let frames = try JSONDecoder().decode([Frame].self, from: Data(contentsOf: manifestURL))
guard !frames.isEmpty else { fatalError("no frames to encode") }
let outputWidth = 1200
let outputHeight = 1024
guard let destination = CGImageDestinationCreateWithURL(
    outputURL as CFURL,
    UTType.gif.identifier as CFString,
    frames.count,
    nil
) else {
    fatalError("could not create GIF destination")
}

CGImageDestinationSetProperties(destination, [
    kCGImagePropertyGIFDictionary: [
        kCGImagePropertyGIFLoopCount: 0,
    ],
] as CFDictionary)

for frame in frames {
    let imageURL = URL(fileURLWithPath: frame.path)
    guard let bitmap = NSImage(contentsOf: imageURL) else {
        fatalError("could not open frame \(frame.path)")
    }
    var proposedRect = CGRect(origin: .zero, size: bitmap.size)
    guard let image = bitmap.cgImage(forProposedRect: &proposedRect, context: nil, hints: nil) else {
        fatalError("could not rasterize frame \(frame.path)")
    }
    guard let context = CGContext(
        data: nil,
        width: outputWidth,
        height: outputHeight,
        bitsPerComponent: 8,
        bytesPerRow: 0,
        space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    ) else {
        fatalError("could not create resized frame context")
    }
    context.interpolationQuality = .high
    context.draw(image, in: CGRect(x: 0, y: 0, width: outputWidth, height: outputHeight))
    guard let resized = context.makeImage() else {
        fatalError("could not resize frame \(frame.path)")
    }
    CGImageDestinationAddImage(destination, resized, [
        kCGImagePropertyGIFDictionary: [
            kCGImagePropertyGIFDelayTime: frame.delay,
            kCGImagePropertyGIFUnclampedDelayTime: frame.delay,
        ],
    ] as CFDictionary)
}

guard CGImageDestinationFinalize(destination) else {
    fatalError("could not finalize GIF")
}
