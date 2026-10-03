import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences_platform_interface/shared_preferences_platform_interface.dart';
import 'package:shared_preferences_platform_interface/types.dart';

bool get _portable => Platform.isWindows;

Future<Directory> applicationDataDirectory() async {
  if (!_portable) return getApplicationSupportDirectory();
  final directory = Directory(
    path.join(path.dirname(Platform.resolvedExecutable), 'userdata'),
  );
  await directory.create(recursive: true);
  return directory;
}

Future<void> installPortablePreferences() async {
  if (!_portable) return;
  final directory = await applicationDataDirectory();
  SharedPreferencesStorePlatform.instance = PortablePreferencesStore(
    File(path.join(directory.path, 'preferences.json')),
  );
}

class PortablePreferencesStore extends SharedPreferencesStorePlatform {
  PortablePreferencesStore(this.file);

  final File file;

  Future<Map<String, Object>> _read() async {
    if (!await file.exists()) return <String, Object>{};
    final decoded = jsonDecode(await file.readAsString());
    if (decoded is! Map) return <String, Object>{};
    return <String, Object>{
      for (final entry in decoded.entries)
        if (entry.key is String && entry.value != null)
          entry.key as String: entry.value as Object,
    };
  }

  Future<bool> _write(Map<String, Object> values) async {
    try {
      await file.parent.create(recursive: true);
      await file.writeAsString(jsonEncode(values), flush: true);
      return true;
    } catch (_) {
      return false;
    }
  }

  Map<String, Object> _filtered(
    Map<String, Object> values,
    PreferencesFilter filter,
  ) {
    final allowList = filter.allowList;
    return <String, Object>{
      for (final entry in values.entries)
        if (entry.key.startsWith(filter.prefix) &&
            (allowList == null || allowList.contains(entry.key)))
          entry.key: entry.value,
    };
  }

  @override
  Future<Map<String, Object>> getAll() async {
    try {
      return await _read();
    } catch (_) {
      return <String, Object>{};
    }
  }

  @override
  Future<bool> setValue(String valueType, String key, Object value) async {
    final values = await getAll();
    values[key] = value;
    return _write(values);
  }

  @override
  Future<bool> remove(String key) async {
    final values = await getAll();
    if (!values.containsKey(key)) return true;
    values.remove(key);
    return _write(values);
  }

  @override
  Future<bool> clear() => _write(<String, Object>{});

  @override
  Future<Map<String, Object>> getAllWithParameters(
    GetAllParameters parameters,
  ) async => _filtered(await getAll(), parameters.filter);

  @override
  Future<bool> clearWithParameters(ClearParameters parameters) async {
    final values = await getAll();
    for (final key in _filtered(values, parameters.filter).keys) {
      values.remove(key);
    }
    return _write(values);
  }
}
