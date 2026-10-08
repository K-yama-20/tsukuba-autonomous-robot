#include "emc270/messages.hpp"

namespace emc270 {
namespace {

bool Finish(const ByteWriter &writer, std::uint16_t *size) {
  if (!writer.ok() || size == nullptr)
    return false;
  *size = static_cast<std::uint16_t>(writer.size());
  return true;
}

} // namespace

bool EncodeHelloPayload(const HelloPayload &value, std::uint8_t *output,
                        std::size_t capacity, std::uint16_t *size) {
  ByteWriter writer(output, capacity);
  writer.U32(value.session_id);
  writer.U8(value.options);
  return Finish(writer, size);
}

bool DecodeHelloPayload(const Frame &frame, HelloPayload *value) {
  if (value == nullptr)
    return false;
  ByteReader reader(frame.payload.data(), frame.payload_size);
  return reader.U32(&value->session_id) && reader.U8(&value->options) &&
         reader.remaining() == 0;
}

bool EncodeCommandPayload(const CommandPayload &value, std::uint8_t *output,
                          std::size_t capacity, std::uint16_t *size) {
  ByteWriter writer(output, capacity);
  writer.I16(value.x_q10000);
  writer.I16(value.y_q10000);
  writer.U8(value.flags);
  return Finish(writer, size);
}

bool DecodeCommandPayload(const Frame &frame, CommandPayload *value) {
  if (value == nullptr)
    return false;
  ByteReader reader(frame.payload.data(), frame.payload_size);
  return reader.I16(&value->x_q10000) && reader.I16(&value->y_q10000) &&
         reader.U8(&value->flags) && reader.remaining() == 0;
}

bool EncodePresetPayload(const PresetPayload &value, std::uint8_t *output,
                         std::size_t capacity, std::uint16_t *size) {
  ByteWriter writer(output, capacity);
  writer.U16(value.x_negative_mv);
  writer.U16(value.x_positive_mv);
  writer.U16(value.y_negative_mv);
  writer.U16(value.y_positive_mv);
  writer.U16(value.x_seed_mv);
  writer.U16(value.y_seed_mv);
  writer.U16(value.dac_full_scale_mv);
  writer.U16(value.watchdog_ms);
  writer.U16(value.slew_full_scale_ms);
  writer.U16(value.motion_threshold_mm_s);
  writer.U16(value.output_warn_tolerance_mv);
  return Finish(writer, size);
}

bool DecodePresetPayload(const Frame &frame, PresetPayload *value) {
  if (value == nullptr)
    return false;
  ByteReader reader(frame.payload.data(), frame.payload_size);
  return reader.U16(&value->x_negative_mv) &&
         reader.U16(&value->x_positive_mv) &&
         reader.U16(&value->y_negative_mv) &&
         reader.U16(&value->y_positive_mv) && reader.U16(&value->x_seed_mv) &&
         reader.U16(&value->y_seed_mv) &&
         reader.U16(&value->dac_full_scale_mv) &&
         reader.U16(&value->watchdog_ms) &&
         reader.U16(&value->slew_full_scale_ms) &&
         reader.U16(&value->motion_threshold_mm_s) &&
         reader.U16(&value->output_warn_tolerance_mv) &&
         reader.remaining() == 0;
}

bool EncodeEncoderSpeedPayload(const EncoderSpeedPayload &value,
                               std::uint8_t *output, std::size_t capacity,
                               std::uint16_t *size) {
  ByteWriter writer(output, capacity);
  writer.I32(value.left_mm_s);
  writer.I32(value.right_mm_s);
  writer.U16(value.status);
  return Finish(writer, size);
}

bool DecodeEncoderSpeedPayload(const Frame &frame, EncoderSpeedPayload *value) {
  if (value == nullptr)
    return false;
  ByteReader reader(frame.payload.data(), frame.payload_size);
  return reader.I32(&value->left_mm_s) && reader.I32(&value->right_mm_s) &&
         reader.U16(&value->status) && reader.remaining() == 0;
}

bool EncodeEventPayload(const EventPayload &value, std::uint8_t *output,
                        std::size_t capacity, std::uint16_t *size) {
  ByteWriter writer(output, capacity);
  writer.U16(static_cast<std::uint16_t>(value.code));
  writer.U8(value.severity);
  writer.U8(static_cast<std::uint8_t>(value.mode));
  writer.I32(value.detail_a);
  writer.I32(value.detail_b);
  writer.U16(value.target_x_mv);
  writer.U16(value.target_y_mv);
  writer.U16(value.actual_x_mv);
  writer.U16(value.actual_y_mv);
  return Finish(writer, size);
}

bool DecodeEventPayload(const Frame &frame, EventPayload *value) {
  if (value == nullptr)
    return false;
  ByteReader reader(frame.payload.data(), frame.payload_size);
  std::uint16_t code = 0;
  std::uint8_t mode = 0;
  if (!reader.U16(&code) || !reader.U8(&value->severity) || !reader.U8(&mode) ||
      !reader.I32(&value->detail_a) || !reader.I32(&value->detail_b) ||
      !reader.U16(&value->target_x_mv) || !reader.U16(&value->target_y_mv) ||
      !reader.U16(&value->actual_x_mv) || !reader.U16(&value->actual_y_mv) ||
      reader.remaining() != 0) {
    return false;
  }
  value->code = static_cast<EventCode>(code);
  value->mode = static_cast<Mode>(mode);
  return true;
}

bool EncodeStatusPayload(const StatusPayload &value, std::uint8_t *output,
                         std::size_t capacity, std::uint16_t *size) {
  ByteWriter writer(output, capacity);
  writer.U8(static_cast<std::uint8_t>(value.mode));
  writer.U8(value.relay_energized);
  writer.U8(value.config_valid);
  writer.U8(value.encoder_valid);
  writer.U8(value.rearm_required);
  writer.U32(value.warnings);
  writer.U32(value.command_age_ms);
  writer.U32(value.encoder_age_ms);
  writer.I16(value.command_x_q10000);
  writer.I16(value.command_y_q10000);
  writer.U16(value.target_x_mv);
  writer.U16(value.target_y_mv);
  writer.U16(value.actual_x_mv);
  writer.U16(value.actual_y_mv);
  writer.I32(value.left_mm_s);
  writer.I32(value.right_mm_s);
  writer.U32(value.config_generation);
  writer.U16(static_cast<std::uint16_t>(value.last_calibration_failure));
  return Finish(writer, size);
}

bool DecodeStatusPayload(const Frame &frame, StatusPayload *value) {
  if (value == nullptr)
    return false;
  ByteReader reader(frame.payload.data(), frame.payload_size);
  std::uint8_t mode = 0;
  std::uint16_t failure = 0;
  if (!reader.U8(&mode) || !reader.U8(&value->relay_energized) ||
      !reader.U8(&value->config_valid) || !reader.U8(&value->encoder_valid) ||
      !reader.U8(&value->rearm_required) || !reader.U32(&value->warnings) ||
      !reader.U32(&value->command_age_ms) ||
      !reader.U32(&value->encoder_age_ms) ||
      !reader.I16(&value->command_x_q10000) ||
      !reader.I16(&value->command_y_q10000) ||
      !reader.U16(&value->target_x_mv) || !reader.U16(&value->target_y_mv) ||
      !reader.U16(&value->actual_x_mv) || !reader.U16(&value->actual_y_mv) ||
      !reader.I32(&value->left_mm_s) || !reader.I32(&value->right_mm_s) ||
      !reader.U32(&value->config_generation) || !reader.U16(&failure) ||
      reader.remaining() != 0) {
    return false;
  }
  value->mode = static_cast<Mode>(mode);
  value->last_calibration_failure = static_cast<CalibrationFailure>(failure);
  return true;
}

bool EncodeAckPayload(const AckPayload &value, std::uint8_t *output,
                      std::size_t capacity, std::uint16_t *size) {
  ByteWriter writer(output, capacity);
  writer.U8(static_cast<std::uint8_t>(value.request_type));
  writer.U8(value.accepted);
  writer.U16(value.reason);
  writer.I32(value.detail);
  return Finish(writer, size);
}

bool DecodeAckPayload(const Frame &frame, AckPayload *value) {
  if (value == nullptr)
    return false;
  ByteReader reader(frame.payload.data(), frame.payload_size);
  std::uint8_t request_type = 0;
  if (!reader.U8(&request_type) || !reader.U8(&value->accepted) ||
      !reader.U16(&value->reason) || !reader.I32(&value->detail) ||
      reader.remaining() != 0) {
    return false;
  }
  value->request_type = static_cast<MessageType>(request_type);
  return true;
}

bool EncodeCalibrationSamplePayload(const CalibrationSamplePayload &value,
                                    std::uint8_t *output, std::size_t capacity,
                                    std::uint16_t *size) {
  ByteWriter writer(output, capacity);
  writer.U32(value.session_id);
  writer.U32(value.sample_index);
  writer.U8(value.phase);
  writer.U8(value.axis);
  writer.I8(value.direction);
  writer.U8(value.verdict);
  writer.U16(value.target_x_mv);
  writer.U16(value.target_y_mv);
  writer.U16(value.actual_x_mv);
  writer.U16(value.actual_y_mv);
  writer.I32(value.left_mm_s);
  writer.I32(value.right_mm_s);
  writer.U32(value.stationary_ms);
  writer.U16(static_cast<std::uint16_t>(value.failure));
  return Finish(writer, size);
}

bool DecodeCalibrationSamplePayload(const Frame &frame,
                                    CalibrationSamplePayload *value) {
  if (value == nullptr)
    return false;
  ByteReader reader(frame.payload.data(), frame.payload_size);
  std::uint16_t failure = 0;
  if (!reader.U32(&value->session_id) || !reader.U32(&value->sample_index) ||
      !reader.U8(&value->phase) || !reader.U8(&value->axis) ||
      !reader.I8(&value->direction) || !reader.U8(&value->verdict) ||
      !reader.U16(&value->target_x_mv) || !reader.U16(&value->target_y_mv) ||
      !reader.U16(&value->actual_x_mv) || !reader.U16(&value->actual_y_mv) ||
      !reader.I32(&value->left_mm_s) || !reader.I32(&value->right_mm_s) ||
      !reader.U32(&value->stationary_ms) || !reader.U16(&failure) ||
      reader.remaining() != 0) {
    return false;
  }
  value->failure = static_cast<CalibrationFailure>(failure);
  return true;
}

bool EncodeControllerConfigPayload(const ControllerConfig &value,
                                   std::uint8_t *output, std::size_t capacity,
                                   std::uint16_t *size) {
  ByteWriter writer(output, capacity);
  writer.U16(value.schema_version);
  writer.U32(value.generation);
  const auto write_axis = [&writer](const AxisProfile &axis) {
    writer.U16(axis.negative_mv);
    writer.U16(axis.positive_mv);
    writer.U16(axis.seed_mv);
    writer.U16(axis.neutral_low_mv);
    writer.U16(axis.neutral_high_mv);
    writer.U16(axis.neutral_mid_mv);
  };
  write_axis(value.x);
  write_axis(value.y);
  writer.U16(value.dac_full_scale_mv);
  writer.U16(value.watchdog_ms);
  writer.U16(value.slew_full_scale_ms);
  writer.U16(value.motion_threshold_mm_s);
  writer.U16(value.output_warn_tolerance_mv);
  writer.U8(value.preset_valid);
  writer.U8(value.neutral_valid);
  return Finish(writer, size);
}

bool DecodeControllerConfigPayload(const Frame &frame,
                                   ControllerConfig *value) {
  if (value == nullptr)
    return false;
  ByteReader reader(frame.payload.data(), frame.payload_size);
  const auto read_axis = [&reader](AxisProfile *axis) {
    return reader.U16(&axis->negative_mv) && reader.U16(&axis->positive_mv) &&
           reader.U16(&axis->seed_mv) && reader.U16(&axis->neutral_low_mv) &&
           reader.U16(&axis->neutral_high_mv) &&
           reader.U16(&axis->neutral_mid_mv);
  };
  return reader.U16(&value->schema_version) && reader.U32(&value->generation) &&
         read_axis(&value->x) && read_axis(&value->y) &&
         reader.U16(&value->dac_full_scale_mv) &&
         reader.U16(&value->watchdog_ms) &&
         reader.U16(&value->slew_full_scale_ms) &&
         reader.U16(&value->motion_threshold_mm_s) &&
         reader.U16(&value->output_warn_tolerance_mv) &&
         reader.U8(&value->preset_valid) && reader.U8(&value->neutral_valid) &&
         reader.remaining() == 0;
}

ControllerConfig ConfigFromPreset(const PresetPayload &preset,
                                  std::uint32_t generation) {
  ControllerConfig config;
  config.generation = generation;
  config.x.negative_mv = preset.x_negative_mv;
  config.x.positive_mv = preset.x_positive_mv;
  config.x.seed_mv = preset.x_seed_mv;
  config.x.neutral_mid_mv = preset.x_seed_mv;
  config.y.negative_mv = preset.y_negative_mv;
  config.y.positive_mv = preset.y_positive_mv;
  config.y.seed_mv = preset.y_seed_mv;
  config.y.neutral_mid_mv = preset.y_seed_mv;
  config.dac_full_scale_mv = preset.dac_full_scale_mv;
  config.watchdog_ms = preset.watchdog_ms;
  config.slew_full_scale_ms = preset.slew_full_scale_ms;
  config.motion_threshold_mm_s = preset.motion_threshold_mm_s;
  config.output_warn_tolerance_mv = preset.output_warn_tolerance_mv;
  config.preset_valid = 1;
  config.neutral_valid = 0;
  return config;
}

PresetPayload PresetFromConfig(const ControllerConfig &config) {
  PresetPayload preset;
  preset.x_negative_mv = config.x.negative_mv;
  preset.x_positive_mv = config.x.positive_mv;
  preset.y_negative_mv = config.y.negative_mv;
  preset.y_positive_mv = config.y.positive_mv;
  preset.x_seed_mv = config.x.seed_mv;
  preset.y_seed_mv = config.y.seed_mv;
  preset.dac_full_scale_mv = config.dac_full_scale_mv;
  preset.watchdog_ms = config.watchdog_ms;
  preset.slew_full_scale_ms = config.slew_full_scale_ms;
  preset.motion_threshold_mm_s = config.motion_threshold_mm_s;
  preset.output_warn_tolerance_mv = config.output_warn_tolerance_mv;
  return preset;
}

} // namespace emc270
