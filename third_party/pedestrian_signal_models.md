# Pedestrian signal model notices

The setup script downloads these unmodified ONNX artifacts to the local Gouda workspace. They are not checked into this source repository.

| Role | Artifact | Immutable source revision | SHA-256 | Size | License |
| --- | --- | --- | --- | ---: | --- |
| Detector | `tlr_car_ped_yolox_s_batch_1.onnx` | [AutowareFoundation/traffic_light_fine_detector](https://huggingface.co/AutowareFoundation/traffic_light_fine_detector/commit/3f0616ffda0c19fc84fc455f988421c0df970e5d) | `1ad633066a1195006f4709f8fa07800dd65a74a814b3efb4c99bcc5a1a7962f6` | 35,794,092 bytes | Apache-2.0 |
| Classifier | `ped_traffic_light_classifier_mobilenetv2_batch_1.onnx` | [AutowareFoundation/traffic_light_classifier](https://huggingface.co/AutowareFoundation/traffic_light_classifier/commit/527c4905afd8f1bfcc03253529a105f7fa5a6d36) | `b52632fee96d1bc99922e743335ebfd49d6a0645c8a04e615f156e38661add24` | 8,885,654 bytes | Apache-2.0 |

The model cards identify both repositories as Apache-2.0. A local copy of the [Apache License, Version 2.0](licenses/Apache-2.0.txt) is included with this notice; the authoritative text is also available from the [Apache Software Foundation](https://www.apache.org/licenses/LICENSE-2.0.txt). The detector card describes a YOLOX-s model for refining a supplied traffic-light region; the classifier card describes red, green, and unknown pedestrian-signal classes. Upstream evaluation and training descriptions do not establish performance for this project's camera or operating conditions.
