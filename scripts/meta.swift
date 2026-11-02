// Prints capture date and GPS for each image or video path listed (one per line) in argv[1].
// Images are read through ImageIO (handles HEIC), videos through AVFoundation.
// Output TSV: path, date ("YYYY:MM:DD HH:MM:SS" or ""), date_source, lat, lon
import AVFoundation
import Foundation
import ImageIO

let videoExts: Set<String> = ["mov", "mp4", "m4v", "3gp", "avi", "mkv", "mts", "m2ts", "wmv", "webm"]

func imageMeta(_ path: String) -> (String, String, String, String) {
    var date = "", source = "", lat = "", lon = ""
    if let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
       let props = CGImageSourceCopyPropertiesAtIndex(src, 0, nil) as? [String: Any] {
        let exif = props["{Exif}"] as? [String: Any]
        let tiff = props["{TIFF}"] as? [String: Any]
        if let v = exif?["DateTimeOriginal"] as? String { date = v; source = "exif" }
        else if let v = exif?["DateTimeDigitized"] as? String { date = v; source = "exif" }
        else if let v = tiff?["DateTime"] as? String { date = v; source = "tiff" }
        if let gps = props["{GPS}"] as? [String: Any],
           let la = gps["Latitude"] as? Double, let lo = gps["Longitude"] as? Double {
            lat = String((gps["LatitudeRef"] as? String) == "S" ? -la : la)
            lon = String((gps["LongitudeRef"] as? String) == "W" ? -lo : lo)
        }
    }
    return (date, source, lat, lon)
}

func videoMeta(_ path: String) async -> (String, String, String, String) {
    var date = "", source = "", lat = "", lon = ""
    // "+50.0614+019.9366+250.000/" -> latitude, longitude
    let iso6709 = try! Regex(#"^([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)"#, as: (Substring, Substring, Substring).self)
    let asset = AVURLAsset(url: URL(fileURLWithPath: path))
    let items = (try? await asset.load(.metadata)) ?? []
    for item in items {
        let key = item.identifier?.rawValue ?? ""
        guard let value = try? await item.load(.stringValue) else { continue }
        if key.hasSuffix("com.apple.quicktime.creationdate"), value.count >= 19 {
            // "2025-11-23T10:46:44+0100": keep the local wall-clock time, like EXIF does.
            date = value.prefix(19).replacingOccurrences(of: "-", with: ":")
                .replacingOccurrences(of: "T", with: " ")
            source = "video"
        } else if key.contains("ISO6709") || key.hasSuffix("xyz"),
                  let m = value.firstMatch(of: iso6709) {
            lat = String(m.output.1); lon = String(m.output.2)
        }
    }
    // Fallback: the container's creation time (UTC), shown in this Mac's time zone.
    // Ignore the 1904/1970 placeholders some apps write.
    if date.isEmpty, let item = try? await asset.load(.creationDate),
       let d = try? await item.load(.dateValue), d > Date(timeIntervalSince1970: 788918400) {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy:MM:dd HH:mm:ss"
        date = f.string(from: d); source = "video"
    }
    return (date, source, lat, lon)
}

let list = try! String(contentsOfFile: CommandLine.arguments[1], encoding: .utf8)
for path in list.split(separator: "\n").map(String.init) {
    let ext = (path as NSString).pathExtension.lowercased()
    let (date, source, lat, lon) = videoExts.contains(ext) ? await videoMeta(path) : imageMeta(path)
    print("\(path)\t\(date)\t\(source)\t\(lat)\t\(lon)")
}
