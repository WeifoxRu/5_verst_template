/**
 * УНИВЕРСАЛЬНЫЙ БЭКЕНД ЛОКАЦИИ (ШАБЛОН)
 * Этот код клонируется для каждого парка.
 * Все данные (токены, пароли) берутся динамически из Registry.
 */

const PROPS = PropertiesService.getScriptProperties();

// ID твоей центральной базы Registry (DATABASE)
const DATABASE_ID = "1zf4IhKNLsAwvp_PKcM3FRZ9C6vYvwtRhfRktMMcYjQM"; 

/**
 * ПОЛУЧЕНИЕ КОНФИГА ПАРКА
 * Скрипт берет свой LOCATION_ID из свойств и ищет свои данные в Registry
 */
function getMyConfig() {
  const locId = PROPS.getProperty('LOCATION_ID'); // Устанавливается Фабрикой при создании
  if (!locId) return null;

  const db = SpreadsheetApp.openById(DATABASE_ID);
  const sheet = db.getSheetByName("Registry");
  const data = sheet.getDataRange().getValues();

  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim() === String(locId).trim()) {
      return {
        location_id: data[i][0],
        park_name: data[i][1],
        event_id: data[i][2],
        sheet_id: data[i][3],
        vk_token: data[i][4],
        nrms_user: data[i][5],
        nrms_pass: data[i][6],
        vk_app_id: data[i][7],
        chat_id: data[i][8] || "2000000001"
      };
    }
  }
  return null;
}

// УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ДАТЫ
function getTargetDate(baseDate) {
  var now = baseDate ? new Date(baseDate) : new Date();
  var moscowString = now.toLocaleString("en-US", {timeZone: "Europe/Moscow"});
  var moscowTime = new Date(moscowString);
  var day = moscowTime.getDay(); 
  var hour = moscowTime.getHours();
  var daysAhead = (6 - day + 7) % 7;
  if (daysAhead === 0 && hour >= 11) {
    daysAhead = 7;
  }
  var target = new Date(moscowTime.getTime() + (daysAhead * 24 * 60 * 60 * 1000));
  return Utilities.formatDate(target, "GMT+3", "dd.MM.yyyy");
}

function getAuthToken(config) {
  let user = config.nrms_user;
  const pass = config.nrms_pass;
  if (!user || !pass) return null;
  if (!user.toUpperCase().startsWith('A')) user = 'A' + user;
  const options = {
    'method': 'post', 'contentType': 'application/json',
    'payload': JSON.stringify({ "username": user, "password": pass }),
    'muteHttpExceptions': true
  };
  try {
    const res = UrlFetchApp.fetch('https://nrms.5verst.ru/api/v1/auth/login', options);
    return JSON.parse(res.getContentText()).result.token;
  } catch (e) { return null; }
}

// Функция для маппинга ролей перед отправкой в NRMS
function mapRoleForNrms(roleId) {
  if (roleId == 1001 || roleId == 1002 || roleId == 1003) return 8;
  if (roleId == 1004) return 10;
  return Number(roleId);
}

function syncToNrms(volunteersList) {
  const config = getMyConfig();
  if (!config) return;
  
  const token = getAuthToken(config);
  if (!token) return;
  
  const currentTarget = getTargetDate();
  let volunteers = volunteersList;

  if (!volunteers) {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Queue");
    const data = sheet.getDataRange().getValues();
    volunteers = [];
    for (let i = 1; i < data.length; i++) {
      if (data[i][0] && data[i][1] && getTargetDate(data[i][5]) === currentTarget) {
        volunteers.push({ 
          "verst_id": Number(data[i][0]), 
          "role_id": mapRoleForNrms(data[i][1]) 
        });
      }
    }
  } else {
    volunteers = volunteers.map(v => ({
      "verst_id": Number(v.verst_id),
      "role_id": mapRoleForNrms(v.role_id)
    }));
  }

  UrlFetchApp.fetch("https://nrms.5verst.ru/api/v1/volunteer/event/save", {
    "method": "post", "contentType": "application/json",
    "headers": { "Authorization": "Bearer " + token },
    "payload": JSON.stringify({ "event_id": Number(config.event_id), "date": currentTarget, "upload_status_id": 1, "volunteers": volunteers }),
    "muteHttpExceptions": true
  });
}

function syncUserStats(vkId, verstId, forceName) {
  const config = getMyConfig();
  if (!config) return null;
  
  const token = getAuthToken(config);
  if (!token) return null;
  
  try {
    const res = UrlFetchApp.fetch("https://nrms.5verst.ru/api/v1/website/athlete/statById", {
      'method': 'post', 'contentType': 'application/json',
      'headers': { 'Authorization': 'Bearer ' + token },
      'payload': JSON.stringify({ "id": Number(verstId) }),
      'muteHttpExceptions': true
    });
    const result = JSON.parse(res.getContentText()).result;
    if (!result) return null;
    const pb = result.personal_best || {};
    const stats = {
      vk_id: vkId, verst_id: verstId, name: forceName || result.full_name,
      runs: pb.total_finishes || 0, vols: pb.volunteering_count || 0,
      run_club: pb.club_membership?.run || "", vol_club: pb.club_membership?.volunteer || ""
    };
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Stats");
    const data = sheet.getDataRange().getValues();
    let rowIdx = -1;
    for (let i = 1; i < data.length; i++) {
      if (data[i][1] == verstId) { rowIdx = i + 1; break; }
    }
    const rowData = [vkId, stats.verst_id, stats.name, stats.runs, stats.vols, stats.run_club, stats.vol_club, new Date()];
    if (rowIdx !== -1) { sheet.getRange(rowIdx, 1, 1, 8).setValues([rowData]); } 
    else { sheet.appendRow(rowData); }
    return stats;
  } catch (e) { return null; }
}

function doGet(e) {
  const config = getMyConfig();
  if (!config) return createJsonResponse({error: "Location configuration not found in Registry"});

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const qSheet = ss.getSheetByName("Queue");
  const sSheet = ss.getSheetByName("Stats");
  const currentTarget = getTargetDate();

  if (e.parameter.get_theme) {
    return createJsonResponse({ theme: PROPS.getProperty('EVENT_THEME') || "" });
  }

  if (e.parameter.get_rating) {
    const data = sSheet.getDataRange().getValues();
    return createJsonResponse(data.slice(1).map(r => ({ name: r[2], verst_id: r[1], runs: r[3], vols: r[4], run_club: r[5], vol_club: r[6] })));
  }

  if (e.parameter.check_vk_id) {
    const vkId = e.parameter.check_vk_id;
    const sData = sSheet.getDataRange().getValues();
    let user = sData.reverse().find(r => r[0] == vkId);
    if (user) return createJsonResponse({ found: true, verst_id: user[1], full_name: user[2] });
    return createJsonResponse({ found: false });
  }

  if (e.parameter.get_date) return createJsonResponse({ date: currentTarget, park_name: config.park_name });

  if (e.parameter.search) {
    const token = getAuthToken(config);
    const query = e.parameter.search.trim();
    const cleanId = query.replace(/^A/i, '');
    const isIdSearch = /^\d+$/.test(cleanId);
    const url = isIdSearch ? 'https://nrms.5verst.ru/api/v1/athlete/getListByIdPart' : 'https://nrms.5verst.ru/api/v1/athlete/getListByNamePart';
    const payload = isIdSearch ? { "id": Number(cleanId) } : { "name": query.toUpperCase(), "event_id": Number(config.event_id), "registered_only": false };
    const res = UrlFetchApp.fetch(url, { 'method': 'post', 'contentType': 'application/json', 'payload': JSON.stringify(payload), 'headers': { 'Authorization': 'Bearer ' + token } });
    return ContentService.createTextOutput(res.getContentText()).setMimeType(ContentService.MimeType.JSON);
  }

  try {
    const data = qSheet.getDataRange().getValues();
    const result = data.slice(1).filter(r => {
      if (!r[5]) return false;
      return getTargetDate(r[5]) === currentTarget;
    }).map(r => ({
      verst_id: r[0], role_id: r[1], role_name: r[2], full_name: r[3],
      author_vk_id: r[4] === "new" ? r[6] : (r[9] || r[6]), vk_id: r[6], comment: r[8] || ""
    }));
    return createJsonResponse(result);
  } catch(err) { return createJsonResponse([]); }
}

function doPost(e) {
  const config = getMyConfig();
  if (!config) return createJsonResponse({success: false, error: "Config missing"});

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const qSheet = ss.getSheetByName("Queue");
  try {
    const data = JSON.parse(e.postData.contents);

    if (data.action === "iot_control") {
      console.log("IoT Command Received: " + data.command);
      return createJsonResponse({ 
        success: true, 
        message: "Command sent to UNIT-" + config.event_id,
        device_response: "ACK" 
      });
    }

    const currentTarget = getTargetDate();

    // Сохранение темы
    if (data.action === "set_theme") {
      PROPS.setProperty('EVENT_THEME', data.theme);
      return createJsonResponse({ success: true });
    }

    // --- 1. УДАЛЕНИЕ ---
    if (data.action === "delete") {
      const qData = qSheet.getDataRange().getValues();
      let volunteersForNrms = [];
      let foundRow = -1;

      for (let i = 1; i < qData.length; i++) {
        let rowVkId = qData[i][6] ? qData[i][6].toString().split('.')[0] : "";
        let reqVkId = data.vk_id ? data.vk_id.toString().split('.')[0] : "";
        let rowRoleId = qData[i][1] ? qData[i][1].toString() : "";
        let reqRoleId = data.role_id ? data.role_id.toString() : "";

        if (rowVkId === reqVkId && rowRoleId === reqRoleId && getTargetDate(qData[i][5]) === currentTarget) {
          foundRow = i + 1;
        } else if (getTargetDate(qData[i][5]) === currentTarget && qData[i][0] && qData[i][1]) {
          volunteersForNrms.push({ "verst_id": Number(qData[i][0]), "role_id": qData[i][1] });
        }
      }

      if (foundRow !== -1) {
        qSheet.deleteRow(foundRow);
        SpreadsheetApp.flush();
        sendDeletionNotice(config, data.person_name || data.full_name || "Волонтер", data.role_name);
      }
      syncToNrms(volunteersForNrms);
      return createJsonResponse({ success: true });
    }

    // --- 2. ВАЛИДАЦИЯ ДЛЯ ЗАПИСИ (МУЛЬТИ) ---
    if (!data.full_name || !data.roles || data.roles.length === 0) {
      return createJsonResponse({ success: false, error: "Missing name or roles" });
    }

    // --- 3. ЗАПИСЬ (ЦИКЛ ПО РОЛЯМ) ---
    const qData = qSheet.getDataRange().getValues();
    let chatRoles = [];

    data.roles.forEach(roleObj => {
      let existingIdx = -1;
      for (let i = 1; i < qData.length; i++) {
        if (getTargetDate(qData[i][5]) === currentTarget && qData[i][0] == data.verst_id && qData[i][1] == roleObj.id) {
          existingIdx = i + 1;
          break;
        }
      }

      if (existingIdx !== -1) {
        qSheet.getRange(existingIdx, 9).setValue(roleObj.comment || "");
      } else {
        qSheet.appendRow([
          data.verst_id.toString(), roleObj.id, roleObj.name, data.full_name, "new", 
          new Date(), data.target_vk_id || data.author_vk_id || "0",   
          data.target_vk_name || data.full_name || "", 
          roleObj.comment || "", data.author_vk_id || "0"
        ]);
      }
      chatRoles.push(roleObj.name + (roleObj.comment ? " (" + roleObj.comment + ")" : ""));
    });

    syncUserStats(data.target_vk_id || data.author_vk_id, data.verst_id, data.full_name);

    if (!(data.silent === true || data.silent === "true")) {
      sendRosterToChat(config, { 
        name: data.full_name, 
        role: chatRoles.join(", "), 
        is_update: false, 
        target_vk: data.target_vk_id || data.author_vk_id, 
        verst_id: data.verst_id
      });
    }

    SpreadsheetApp.flush();
    syncToNrms();
    return createJsonResponse({ success: true });

  } catch (err) { return createJsonResponse({ success: false, error: err.toString() }); }
}

function createJsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function getRandomId() { return Math.floor(Math.random() * 2147483647).toString(); }

function sendDeletionNotice(config, name, role) {
  const msg = "❌ Отмена записи:\n" + name + " удалился(лась) с позиции " + role;
  const url = "https://api.vk.com/method/messages.send";
  const payload = {
    'access_token': config.vk_token,
    'peer_id': config.chat_id,
    'message': msg,
    'random_id': getRandomId(),
    'v': '5.131'
  };
  UrlFetchApp.fetch(url, { 'method': 'post', 'payload': payload, 'muteHttpExceptions': true });
}

function sendRosterToChat(config, lastEntry) {
  const currentTarget = getTargetDate();
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Queue");
  const data = sheet.getDataRange().getValues();
  const theme = PROPS.getProperty('EVENT_THEME') || "";
  
  // Шаблон (количество слотов)
  const rosterTemplate = [
    { id: 1, label: "Организатор", count: 1 },
    { id: 35, label: "Разметка трассы", count: 1 },
    { id: 15, label: "Инструктаж новых участников", count: 1 },
    { id: 2, label: "Секундомер", count: 2 },
    { id: 13, label: "Карточки позиций", count: 1 },
    { id: 11, label: "Сканирование штрих-кодов", count: 1 },
    { id: 19, label: "Замыкающий", count: 1 },
    { id: 7, label: "Маршал", count: 1 },
    { id: 31, label: "Проведение разминки", count: 1 },
    { id: 8, label: "Подготовка мероприятия", count: 1 },
    { id: 1001, label: "Чай", count: 1 },
    { id: 1002, label: "Вкусняшки", count: 1 },
    { id: 1003, label: "Вода", count: 1 },
    { id: 1004, label: "Поддержка на трассе", count: 1},
    { id: 5, label: "Фотограф", count: 1 },
    { id: 38, label: "Видеограф", count: 1 }
  ]; 
  
  let msg = theme ? theme + "\n\n" : "";

  if (lastEntry && lastEntry.role && lastEntry.role !== "undefined") {
    const mention = "[id" + lastEntry.target_vk + "|" + lastEntry.name + "]";
    msg += (lastEntry.is_update ? "🔄 Обновлено: " : "⚡️ Новая запись: ") + mention + " — " + lastEntry.role + "\n";
    msg += "————————————————\n\n";
  }
  msg += "📅 Список волонтеров на " + currentTarget + "\n\n";
  
  let usedRows = new Set(); 
  
  rosterTemplate.forEach(item => {
    let slotsFound = 0;
    for(let i = 1; i < data.length; i++) {
      if (data[i][1] == item.id && getTargetDate(data[i][5]) === currentTarget) {
        let comment = data[i][8] ? " (" + data[i][8] + ")" : "";
        msg += "⭐ " + item.label + comment + " — [id" + data[i][6] + "|" + data[i][3] + "]\n";
        usedRows.add(i);
        slotsFound++;
      }
    }
    for (let j = slotsFound; j < item.count; j++) {
      msg += "➖ " + item.label + " — \n";
    }
  });

  let extra = "";
  for(let i = 1; i < data.length; i++) {
    if (!usedRows.has(i) && data[i][2] && getTargetDate(data[i][5]) === currentTarget) {
      extra += "⭐ " + data[i][2] + (data[i][8] ? " (" + data[i][8] + ")" : "") + " — [id" + data[i][6] + "|" + data[i][3] + "]\n";
    }
  }
  if (extra) msg += "\n➕ Дополнительно:\n" + extra;
  msg += "\n📝 Записаться: vk.com/app" + config.vk_app_id;
  
  const url = "https://api.vk.com/method/messages.send";
  const payload = {
    'access_token': config.vk_token,
    'peer_id': config.chat_id,
    'message': msg,
    'random_id': getRandomId(),
    'v': '5.131'
  };
  UrlFetchApp.fetch(url, { 'method': 'post', 'payload': payload, 'muteHttpExceptions': true });
}
