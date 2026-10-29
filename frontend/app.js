import { API_BASE_URL } from "./config.js";
import { ApiError, createApiClient } from "./api.js";

export class ValidationError extends Error {}

export function monthToDate(value) {
  if (typeof value !== "string" || !/^[0-9]{4}-(0[1-9]|1[0-2])$/.test(value)
      || Number(value.slice(0, 4)) < 1) {
    throw new ValidationError("월은 0001-01부터 9999-12까지 YYYY-MM 형식으로 입력하세요.");
  }
  return `${value}-01`;
}

export function parseInteger(value) {
  const text = typeof value === "string" ? value.trim() : "";
  if (!/^-?[0-9]+$/.test(text)) {
    throw new ValidationError("순이동자수는 소수·쉼표·지수 표기 없이 정수로 입력하세요. 음수와 0은 가능합니다.");
  }
  const parsed = Number(text);
  if (!Number.isSafeInteger(parsed)) {
    throw new ValidationError("브라우저가 정확하게 처리할 수 있는 정수 범위를 벗어났습니다. ±9,007,199,254,740,991 이내로 입력하세요. 서버의 64비트 정수 범위보다 좁은 제한입니다.");
  }
  return parsed;
}

export function shouldSendOnEnter(event, pending = false) {
  return event.key === "Enter" && !event.shiftKey && !event.isComposing
    && event.keyCode !== 229 && !pending;
}

export function formatNumber(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "자료 없음";
  if (Number.isInteger(value) && !Number.isSafeInteger(value)) return "정확한 표시 범위 초과";
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(value);
}

const ERROR_MESSAGES = Object.freeze({
  access_required: "접근 토큰을 먼저 연결하세요.",
  access_denied: "접근 토큰이 유효하지 않습니다. 토큰을 확인하고 다시 연결하세요.",
  access_not_configured: "서버의 접근 인증 설정을 확인해야 합니다.",
  duplicate_month: "같은 월의 기록이 이미 있습니다. 목록에서 해당 월을 확인하세요.",
  validation_error: "입력 형식이나 길이가 올바르지 않습니다. 월·정수·메모 또는 질문을 확인하세요.",
  data_not_found: "대상 월별 기록이 없습니다. 자료 목록을 새로고침하세요.",
  conversation_not_found: "질문 기록이 없거나 삭제되었습니다. 이전 질문 목록을 새로고침하세요.",
  concurrent_modification: "다른 작업과 변경이 겹쳤습니다. 최신 기록을 불러온 뒤 확인하세요.",
  conversation_changed: "질문 기록이 변경되어 답변을 저장하지 못했습니다. 질문 기록을 확인하세요. AI를 다시 호출하지 않았습니다.",
  conversation_conflict: "다른 요청이 질문 기록을 변경하거나 삭제했습니다. 최신 질문 기록을 확인하세요.",
  conversation_message_limit: "최대 20번의 문답에 도달했습니다. 새 질문 버튼을 눌러 새로 시작하세요.",
  conversation_payload_too_large: "질문 기록의 저장 크기 한도에 도달했습니다. 새 질문 버튼을 눌러 새로 시작하세요.",
  invalid_chat_message: "질문은 앞뒤 공백을 제외하고 1~2,000자로 입력하세요.",
  invalid_conversation_id: "질문 기록 식별자가 올바르지 않습니다. 목록에서 질문 기록을 다시 선택하세요.",
  invalid_conversation_payload: "질문 기록 내용을 저장할 수 있는 형식이 아닙니다. 서버 설정을 확인하세요.",
  conversation_integrity_error: "저장된 질문 기록 형식에 문제가 있습니다. 백엔드에서 기록을 확인해야 합니다.",
  conversation_internal_error: "서버에서 질문 기록 요청을 처리하지 못했습니다. 서버 상태를 확인하세요.",
  conversation_save_unconfirmed: "질문 기록 저장 결과를 확인하지 못했습니다. 다시 생성하기 전에 기록을 확인하세요.",
  month_change_not_supported: "기존 기록의 월은 변경할 수 없습니다.",
  data_empty: "저장 자료가 없어 분석할 수 없습니다. AI는 호출되지 않았습니다.",
  database_unavailable: "데이터베이스에 연결할 수 없습니다. 백엔드와 Firebase 연결 상태를 확인하세요.",
  data_integrity_error: "저장 자료의 형식에 문제가 있습니다. 백엔드에서 자료를 확인해야 합니다.",
  internal_error: "서버에서 요청을 처리하지 못했습니다. 서버 상태를 확인하세요.",
  openai_authentication_failed: "AI 인증에 실패했습니다. 백엔드에 등록된 코디세이 키의 사용 상태를 확인하세요.",
  openai_access_denied: "AI 모델 또는 프로젝트의 접근 권한을 확인해야 합니다.",
  openai_quota_unavailable: "AI 사용 한도 또는 크레딧을 확인해야 합니다. 코디세이 지원 계정의 상태를 확인하세요.",
  openai_rate_limited: "AI 요청 빈도 제한에 도달했습니다. 자동 재전송하지 않았습니다.",
  openai_model_unavailable: "현재 설정된 AI 모델을 사용할 수 없습니다. 백엔드 설정을 확인하세요.",
  openai_configuration_error: "AI 연결 또는 요청 설정을 확인해야 합니다.",
  openai_configuration_missing: "백엔드의 AI 연결 설정이 준비되지 않았습니다.",
  openai_timeout: "AI 응답 시간이 초과되었습니다. 자동 재전송하지 않았습니다.",
  openai_connection_failed: "AI 제공자와의 통신에 실패했습니다. 자동 재전송하지 않았습니다.",
  openai_request_failed: "AI 답변 생성에 실패했습니다. 자동 재전송하지 않았습니다.",
  openai_response_incomplete: "답변이 잘렸거나 정상 완료되지 않아 저장하지 않았습니다.",
  openai_response_refused: "AI가 답변을 제공하지 않아 저장하지 않았습니다.",
  openai_response_empty: "AI 답변이 비어 있어 저장하지 않았습니다.",
  openai_response_too_long: "답변이 저장 길이 제한을 초과해 저장하지 않았습니다.",
  openai_response_failed: "AI 응답에 오류가 있어 저장하지 않았습니다.",
  openai_response_invalid: "AI 응답 형식을 확인할 수 없어 저장하지 않았습니다.",
  openai_invalid_response: "AI 응답 형식을 확인할 수 없어 저장하지 않았습니다.",
  chat_save_failed: "답변은 생성됐지만 자동 저장을 확인하지 못했습니다. 이전 질문 목록을 새로고침해 확인하세요. 저장 검사 때문에 AI를 다시 호출하지 않았습니다.",
  client_timeout: "브라우저의 응답 대기 시간이 끝났습니다.",
  network_error: "서버에 연결하지 못했습니다. 로컬 서버 주소·실행 상태·CORS 설정을 확인하세요.",
  invalid_response: "서버 응답을 읽을 수 없습니다. 현재 결과를 정상 자료로 표시하지 않습니다.",
  invalid_api_configuration: "공개 설정 파일의 FastAPI 주소를 확인하세요.",
});

export function safeErrorMessage(error, { chat = false } = {}) {
  if (error instanceof ValidationError) return error.message;
  const known = Object.hasOwn(ERROR_MESSAGES, error?.code);
  let text = known ? ERROR_MESSAGES[error.code] : ({
    404: "요청한 기록을 찾을 수 없습니다. 목록을 새로고침하세요.",
    409: "현재 저장 상태와 요청이 충돌했습니다. 최신 목록을 확인하세요.",
    422: "입력 형식 또는 길이가 올바르지 않습니다. 입력값을 확인하세요.",
    429: "요청 횟수가 제한되었습니다. 자동 재전송하지 않았습니다.",
    503: "현재 서버 또는 연결 서비스를 사용할 수 없습니다.",
  }[error?.status] || "요청을 완료하지 못했습니다. 서버 상태를 확인하세요.");
  const uncertain = ["client_timeout", "network_error", "openai_timeout", "openai_connection_failed", "invalid_response"].includes(error?.code);
  if (chat && uncertain) {
    text += " 브라우저 대기 종료가 서버 작업 취소를 뜻하지는 않습니다. 완료·저장 여부가 불명확하니 이전 질문 목록을 새로고침해 확인한 뒤 다시 보내세요. 자동 재전송하지 않았습니다.";
  } else if (!chat && ["client_timeout", "network_error"].includes(error?.code)) {
    text += " 변경 요청이었다면 반영 여부를 목록에서 먼저 확인하세요.";
  }
  const status = Number.isInteger(error?.status) && error.status >= 100 && error.status <= 599
    ? `HTTP ${error.status}` : "";
  const code = known ? error.code : "";
  const suffix = [status, code].filter(Boolean).join(" · ");
  return suffix ? `${text} (${suffix})` : text;
}

const SELECTED_KEY = "gajimaiso.selected-conversation-id";
const ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const codePointLength = (text) => Array.from(text).length;
const periodText = (period) => period?.start && period?.end ? `${period.start} ~ ${period.end}` : "비교 기간 없음";

export function startApp() {
  const byId = (id) => document.getElementById(id);
  let accessToken = "";
  let accessPending = false;
  let api;
  try { api = createApiClient(API_BASE_URL, globalThis.fetch, undefined, () => accessToken); } catch (error) {
    byId("connection-status").textContent = "연결 설정 확인 필요";
    ["summary-state", "conversation-list-state", "data-list-state"].forEach((id) => {
      byId(id).textContent = safeErrorMessage(error);
      byId(id).dataset.tone = "error";
    });
    document.querySelectorAll("button, input, textarea").forEach((element) => { element.disabled = true; });
    return;
  }
  const state = {
    conversations: [], conversationId: null, conversation: null, messages: [],
    chatPending: false, composing: false, conversationBusy: false, conversationLoading: false,
    conversationsLoading: false, detailVersion: 0, listVersion: 0,
    data: [], editingRecord: null, dataBusy: false, dataLoading: false, summaryLoading: false,
    summaryVersion: 0, dataVersion: 0,
  };
  const welcome = byId("messages").firstElementChild.cloneNode(true);

  function notice(id, text, tone = "info") {
    const element = byId(id);
    element.textContent = text;
    element.dataset.tone = tone;
    element.hidden = !text;
  }
  function persistSelection(id) {
    try {
      if (id) localStorage.setItem(SELECTED_KEY, id);
      else localStorage.removeItem(SELECTED_KEY);
    } catch { /* Storage restrictions do not prevent server-backed conversations. */ }
  }
  function restoreSelection() {
    try {
      const value = localStorage.getItem(SELECTED_KEY);
      return ID_PATTERN.test(value || "") ? value : null;
    } catch { return null; }
  }
  function element(tag, className, text) {
    const result = document.createElement(tag);
    if (className) result.className = className;
    if (text !== undefined) result.textContent = text;
    return result;
  }
  function dateTimeText(value) {
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return "저장 시각 확인 불가";
    return new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
  }
  function updateControls() {
    const question = byId("chat-question").value.trim();
    const length = codePointLength(question);
    const locked = state.chatPending || state.conversationBusy || accessPending;
    byId("access-connect").disabled = locked || state.dataBusy;
    byId("access-token").disabled = locked || state.dataBusy;
    byId("access-clear").disabled = locked || state.dataBusy || !accessToken;
    byId("new-conversation").disabled = locked;
    byId("conversations-refresh").disabled = locked || state.conversationsLoading;
    byId("delete-conversation").disabled = locked || state.conversationLoading;
    byId("chat-question").disabled = state.chatPending;
    byId("send-question").disabled = !accessToken || locked || state.conversationLoading || state.dataBusy || state.composing || length < 1 || length > 2000;
    byId("send-label").textContent = state.chatPending ? "답변 대기 중" : "보내기";
    byId("chat-form").setAttribute("aria-busy", String(state.chatPending));
    byId("chat-character-count").textContent = `${formatNumber(length)} / 2,000자`;
    byId("chat-character-count").dataset.invalid = String(length > 2000);
    byId("chat-question").setAttribute("aria-invalid", String(length > 2000));
    document.querySelectorAll(".conversation-button, .example-question").forEach((button) => { button.disabled = locked; });
    byId("summary-refresh").disabled = state.summaryLoading;
    byId("data-refresh").disabled = state.dataLoading || state.dataBusy;
    const dataLocked = !accessToken || accessPending || state.dataBusy || state.chatPending;
    ["data-value", "data-memo", "data-submit", "data-cancel"].forEach((id) => { byId(id).disabled = dataLocked; });
    byId("data-month").disabled = dataLocked || Boolean(state.editingRecord);
    byId("data-submit").textContent = state.dataBusy ? "처리 중…" : state.editingRecord ? "수정 저장" : "기록 추가";
    document.querySelectorAll(".row-button").forEach((button) => { button.disabled = dataLocked || button.dataset.unsafe === "true"; });
  }

  function numberWithUnit(id, value) {
    const target = byId(id);
    target.replaceChildren(document.createTextNode(formatNumber(value)));
    if (typeof value === "number" && Number.isFinite(value)) target.append(element("small", "", "명"));
  }
  async function loadSummary() {
    const version = ++state.summaryVersion;
    state.summaryLoading = true;
    byId("summary-content").hidden = true;
    notice("summary-state", "현재 저장 자료를 불러오고 있습니다.");
    updateControls();
    try {
      const summary = await api("/api/data/summary");
      if (version !== state.summaryVersion) return;
      if (!Number.isInteger(summary?.count) || summary.count < 0 || !summary.metrics || !summary.trend) throw new ApiError("invalid_response");
      byId("connection-status").textContent = "저장 자료 연결됨";
      byId("connection-status").dataset.connected = "true";
      if (summary.count === 0) {
        notice("summary-state", "저장된 월별 자료가 없습니다. 자료를 추가한 뒤 요약을 확인할 수 있습니다.");
        return;
      }
      notice("summary-state", "");
      byId("summary-content").hidden = false;
      byId("summary-period").textContent = `분석 기간 ${periodText(summary.period)}`;
      byId("summary-count").textContent = `${formatNumber(summary.count)}개 월별 기록`;
      byId("summary-latest").textContent = `최신 저장 월 ${summary.latest?.month || "확인 불가"}`;
      numberWithUnit("summary-average", summary.metrics.average);
      numberWithUnit("summary-recent", summary.trend.recent_average);
      numberWithUnit("summary-previous", summary.trend.previous_average);
      numberWithUnit("summary-difference", summary.trend.difference);
      byId("summary-recent-period").textContent = periodText(summary.trend.recent_period);
      byId("summary-previous-period").textContent = periodText(summary.trend.previous_period);
      byId("summary-trend").textContent = summary.trend.description;
      const missing = summary.quality?.missing_months || [];
      byId("summary-quality").hidden = missing.length === 0;
      byId("summary-quality").textContent = missing.length ? `누락 월 ${missing.length}개: ${missing.join(", ")}. 누락값을 채우지 않았습니다.` : "";
    } catch (error) {
      if (version !== state.summaryVersion) return;
      byId("summary-content").hidden = true;
      notice("summary-state", `요약 조회 실패 · ${safeErrorMessage(error)}`, "error");
      byId("connection-status").textContent = "자료 연결 확인 필요";
      byId("connection-status").dataset.connected = "false";
    } finally {
      if (version === state.summaryVersion) { state.summaryLoading = false; updateControls(); }
    }
  }

  function renderConversationList() {
    const list = byId("conversation-list");
    list.replaceChildren();
    for (const item of state.conversations) {
      const li = element("li");
      const button = element("button", "conversation-button");
      button.type = "button";
      button.dataset.id = item.id;
      button.setAttribute("aria-current", String(item.id === state.conversationId));
      button.append(element("strong", "", item.title));
      button.append(element("small", "", `${dateTimeText(item.updated_at)} · 메시지 ${item.message_count}개`));
      li.append(button);
      list.append(li);
    }
    updateControls();
  }
  async function loadConversations() {
    if (!accessToken) {
      notice("conversation-list-state", "접근 토큰을 연결하면 이전 질문을 불러올 수 있습니다.");
      return false;
    }
    const version = ++state.listVersion;
    state.conversationsLoading = true;
    notice("conversation-list-state", "이전 질문 목록을 불러오고 있습니다.");
    state.conversations = [];
    byId("conversation-count").textContent = "";
    renderConversationList();
    try {
      const response = await api("/api/conversations");
      if (version !== state.listVersion) return false;
      if (!Array.isArray(response?.items) || !Number.isInteger(response.count)) throw new ApiError("invalid_response");
      state.conversations = response.items;
      byId("conversation-count").textContent = `${formatNumber(response.count)}건`;
      notice("conversation-list-state", response.count ? "" : "아직 저장된 질문이 없습니다. 첫 질문을 남겨보세요.");
      renderConversationList();
      return true;
    } catch (error) {
      if (version === state.listVersion) notice("conversation-list-state", `목록 조회 실패 · ${safeErrorMessage(error)}`, "error");
      return false;
    } finally {
      if (version === state.listVersion) { state.conversationsLoading = false; updateControls(); }
    }
  }
  function renderMessages(pendingQuestion = null) {
    const container = byId("messages");
    container.replaceChildren();
    if (!state.messages.length && pendingQuestion === null) container.append(welcome.cloneNode(true));
    for (const message of state.messages) appendMessage(message.role, message.content);
    if (pendingQuestion !== null) {
      appendMessage("user", pendingQuestion);
      const waiting = appendMessage("assistant", "현재 저장 자료를 읽고 답변을 준비하고 있습니다. 이 동안 질문 기록을 전환하거나 다시 보내지 마세요.");
      waiting.classList.add("message-pending");
    }
    updateControls();
    container.scrollTop = container.scrollHeight;
  }
  function appendMessage(role, content) {
    const article = element("article", `message ${role === "user" ? "message-user" : "message-assistant"}`);
    article.append(element("p", "message-label", role === "user" ? "나" : "AI 답변"));
    article.append(element("div", "message-body", content));
    byId("messages").append(article);
    return article;
  }
  function renderChatHeader() {
    byId("delete-conversation").hidden = !state.conversationId;
  }
  function newConversation() {
    if (state.chatPending || state.conversationBusy) return;
    state.detailVersion++;
    state.conversationLoading = false;
    state.conversationId = null;
    state.conversation = null;
    state.messages = [];
    persistSelection(null);
    byId("chat-question").value = "";
    notice("chat-feedback", "새 질문입니다. 기존 질문 기록은 삭제하지 않았습니다.");
    renderChatHeader(); renderMessages(); renderConversationList();
    byId("chat-question").focus();
  }
  async function loadConversation(id) {
    if (state.chatPending || state.conversationBusy || !ID_PATTERN.test(id)) return;
    const version = ++state.detailVersion;
    state.conversationLoading = true;
    state.conversationId = null;
    state.conversation = null;
    state.messages = [];
    byId("messages").replaceChildren(element("p", "notice", "저장된 질문과 답변을 불러오고 있습니다. AI를 호출하지 않습니다."));
    byId("delete-conversation").hidden = true;
    notice("chat-feedback", "");
    updateControls();
    try {
      const record = await api(`/api/conversations/${encodeURIComponent(id)}`);
      if (version !== state.detailVersion) return;
      if (record?.id !== id || !Array.isArray(record.messages)) throw new ApiError("invalid_response");
      state.conversationId = record.id;
      state.conversation = record;
      state.messages = record.messages;
      persistSelection(record.id);
      renderChatHeader(); renderMessages(); renderConversationList();
      notice("chat-feedback", "서버에서 저장된 질문 기록을 불러왔습니다. AI를 다시 호출하지 않았습니다.", "success");
    } catch (error) {
      if (version !== state.detailVersion) return;
      persistSelection(null);
      renderChatHeader();
      byId("messages").replaceChildren(element("p", "notice", "질문 기록을 불러오지 못했습니다. 이전 질문 목록에서 다시 선택할 수 있습니다."));
      notice("chat-feedback", safeErrorMessage(error), "error");
    } finally {
      if (version === state.detailVersion) { state.conversationLoading = false; updateControls(); }
    }
  }
  async function sendQuestion(event) {
    event.preventDefault();
    if (state.chatPending || state.conversationBusy || state.conversationLoading || state.dataBusy || state.composing) return;
    const originalInput = byId("chat-question").value;
    const question = originalInput.trim();
    if (codePointLength(question) < 1 || codePointLength(question) > 2000) {
      notice("chat-feedback", "질문은 앞뒤 공백을 제외하고 1~2,000자로 입력하세요.", "error");
      return;
    }
    // Capture the selected server-issued ID once. It cannot change while this request is pending.
    const conversationId = state.conversationId;
    state.detailVersion++;
    state.chatPending = true;
    notice("chat-feedback", "답변 생성과 자동 저장을 기다리고 있습니다. 전송은 한 번만 수행합니다.");
    renderMessages(question);
    updateControls();
    try {
      const response = await api("/api/chat", { method: "POST", kind: "chat", body: { message: question, conversation_id: conversationId } });
      if (response?.saved !== true || !ID_PATTERN.test(response.conversation_id || "")
          || typeof response.reply !== "string" || !response.reply.trim()
          || (conversationId !== null && response.conversation_id !== conversationId)) {
        throw new ApiError("invalid_response");
      }
      state.messages = [...state.messages, { role: "user", content: question }, { role: "assistant", content: response.reply }];
      state.conversationId = response.conversation_id;
      state.conversation = {
        ...(state.conversation || {}), id: response.conversation_id,
        title: state.conversation?.title || "저장된 새 질문", last_model: response.model,
      };
      persistSelection(response.conversation_id);
      byId("chat-question").value = "";
      renderChatHeader(); renderMessages();
      notice("chat-feedback", "자동 저장 완료 · 서버가 질문과 답변의 저장을 확인했습니다.", "success");
      // Chat already saves. Only a list GET is needed; never POST /api/conversations here.
      await loadConversations();
      const listed = state.conversations.find((item) => item.id === state.conversationId);
      if (listed) { state.conversation.title = listed.title; renderChatHeader(); }
    } catch (error) {
      byId("chat-question").value = originalInput;
      renderMessages();
      notice("chat-feedback", `저장 완료로 확인되지 않았습니다. ${safeErrorMessage(error, { chat: true })}`, "error");
    } finally {
      state.chatPending = false;
      updateControls();
    }
  }
  async function deleteConversation() {
    if (!state.conversationId || state.chatPending || state.conversationBusy || state.conversationLoading) return;
    const id = state.conversationId;
    const title = state.conversation?.title || "선택한 질문 기록";
    if (!window.confirm(`“${title}” 질문 기록을 삭제할까요?\n저장된 질문과 답변이 삭제되며 되돌릴 수 없습니다.`)) return;
    state.conversationBusy = true;
    updateControls();
    try {
      await api(`/api/conversations/${encodeURIComponent(id)}`, { method: "DELETE", kind: "write" });
      state.conversationBusy = false;
      newConversation();
      notice("chat-feedback", "선택한 질문 기록을 삭제했습니다.", "success");
      await loadConversations();
    } catch (error) {
      notice("chat-feedback", safeErrorMessage(error), "error");
    } finally { state.conversationBusy = false; updateControls(); }
  }

  function renderData() {
    const rows = byId("data-rows");
    rows.replaceChildren();
    for (const record of [...state.data].sort((a, b) => b.date.localeCompare(a.date))) {
      const tr = element("tr");
      tr.append(element("td", "", record.date.slice(0, 7)));
      tr.append(element("td", "number-cell", formatNumber(record.value)));
      tr.append(element("td", "table-memo", record.memo || "—"));
      const controls = element("td");
      const actions = element("div", "row-actions");
      for (const [action, label] of [["edit", "수정"], ["delete", "삭제"]]) {
        const button = element("button", `row-button ${action === "delete" ? "row-delete" : ""}`, label);
        button.type = "button";
        button.dataset.action = action;
        button.dataset.id = record.id;
        button.dataset.unsafe = String(!Number.isSafeInteger(record.value));
        button.setAttribute("aria-label", `${record.date.slice(0, 7)} 기록 ${label}`);
        actions.append(button);
      }
      controls.append(actions); tr.append(controls); rows.append(tr);
    }
    updateControls();
  }
  async function loadData() {
    const version = ++state.dataVersion;
    state.dataLoading = true;
    state.data = [];
    byId("data-count").textContent = "";
    byId("data-table").hidden = true;
    renderData();
    notice("data-list-state", "현재 월별 자료를 불러오고 있습니다.");
    try {
      const response = await api("/api/data");
      if (version !== state.dataVersion) return;
      if (!Array.isArray(response?.items) || !Number.isInteger(response.count)) throw new ApiError("invalid_response");
      state.data = response.items;
      byId("data-count").textContent = `${formatNumber(response.count)}건`;
      byId("data-table").hidden = response.count === 0;
      notice("data-list-state", response.count === 0 ? "저장된 월별 자료가 없습니다. 왼쪽 입력칸에서 첫 기록을 추가할 수 있습니다." : "");
      renderData();
    } catch (error) {
      if (version === state.dataVersion) notice("data-list-state", `자료 조회 실패 · ${safeErrorMessage(error)}`, "error");
    } finally { if (version === state.dataVersion) { state.dataLoading = false; updateControls(); } }
  }
  function resetDataForm() {
    state.editingRecord = null;
    byId("data-form").reset();
    byId("data-form-title").textContent = "월별 기록 추가";
    byId("data-form-mode").textContent = "새 기록";
    byId("data-month-help").textContent = "YYYY-MM · 저장 시 월 대표일 01을 사용합니다.";
    byId("data-cancel").hidden = true;
    updateControls();
  }
  function editRecord(record) {
    if (state.dataBusy || state.chatPending) return;
    if (!Number.isSafeInteger(record.value)) {
      notice("data-feedback", "브라우저에서 정확히 표현할 수 없는 정수여서 수정할 수 없습니다.", "error");
      return;
    }
    state.editingRecord = record;
    byId("data-month").value = record.date.slice(0, 7);
    byId("data-value").value = String(record.value);
    byId("data-memo").value = record.memo;
    byId("data-form-title").textContent = `${record.date.slice(0, 7)} 기록 수정`;
    byId("data-form-mode").textContent = "수정 중";
    byId("data-month-help").textContent = "기존 기록의 월은 변경할 수 없습니다.";
    byId("data-cancel").hidden = false;
    notice("data-feedback", "실제 저장값을 수정합니다. 내용을 확인한 뒤 수정 저장을 누르세요.");
    updateControls();
    byId("data-value").focus();
  }
  async function saveData(event) {
    event.preventDefault();
    if (state.dataBusy || state.chatPending) return;
    let payload;
    try {
      const memo = byId("data-memo").value;
      if (codePointLength(memo) > 500) throw new ValidationError("메모는 최대 500자로 입력하세요.");
      payload = { date: monthToDate(byId("data-month").value), value: parseInteger(byId("data-value").value), memo };
    } catch (error) { notice("data-feedback", safeErrorMessage(error), "error"); return; }
    const editing = state.editingRecord;
    if (editing && !window.confirm(`${payload.date.slice(0, 7)} 기록을 수정할까요?\n순이동 ${formatNumber(editing.value)}명 → ${formatNumber(payload.value)}명\n메모도 입력한 내용으로 변경됩니다.`)) return;
    state.dataBusy = true;
    notice("data-feedback", "저장 요청을 처리하고 있습니다.");
    updateControls();
    try {
      await api(editing ? `/api/data/${encodeURIComponent(editing.id)}` : "/api/data", { method: editing ? "PUT" : "POST", kind: "write", body: payload });
      resetDataForm();
      notice("data-feedback", `${payload.date.slice(0, 7)} 기록을 ${editing ? "수정" : "추가"}했습니다. 목록과 요약을 갱신합니다.`, "success");
      await Promise.all([loadData(), loadSummary()]);
    } catch (error) { notice("data-feedback", safeErrorMessage(error), "error"); }
    finally { state.dataBusy = false; updateControls(); }
  }
  async function deleteRecord(record) {
    if (state.dataBusy || state.chatPending || !Number.isSafeInteger(record.value)) return;
    if (!window.confirm(`${record.date.slice(0, 7)} · 순이동 ${formatNumber(record.value)}명 기록을 삭제할까요?\n실제 저장 자료에서 삭제되며 되돌릴 수 없습니다.`)) return;
    state.dataBusy = true;
    notice("data-feedback", "삭제 요청을 처리하고 있습니다.");
    updateControls();
    try {
      await api(`/api/data/${encodeURIComponent(record.id)}`, { method: "DELETE", kind: "write" });
      if (state.editingRecord?.id === record.id) resetDataForm();
      notice("data-feedback", `${record.date.slice(0, 7)} 기록을 삭제했습니다. 목록과 요약을 갱신합니다.`, "success");
      await Promise.all([loadData(), loadSummary()]);
    } catch (error) { notice("data-feedback", safeErrorMessage(error), "error"); }
    finally { state.dataBusy = false; updateControls(); }
  }

  byId("summary-refresh").addEventListener("click", loadSummary);
  byId("data-refresh").addEventListener("click", () => Promise.all([loadData(), loadSummary()]));
  byId("conversations-refresh").addEventListener("click", loadConversations);
  byId("new-conversation").addEventListener("click", newConversation);
  byId("delete-conversation").addEventListener("click", deleteConversation);
  byId("conversation-list").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-id]");
    if (button && !button.disabled) loadConversation(button.dataset.id);
  });
  byId("messages").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-example]");
    if (!button || state.chatPending || state.conversationBusy) return;
    byId("chat-question").value = button.dataset.example;
    updateControls();
    byId("chat-question").focus();
  });
  byId("chat-form").addEventListener("submit", sendQuestion);
  byId("chat-question").addEventListener("input", updateControls);
  byId("chat-question").addEventListener("compositionstart", () => { state.composing = true; updateControls(); });
  byId("chat-question").addEventListener("compositionend", () => { state.composing = false; updateControls(); });
  byId("chat-question").addEventListener("keydown", (event) => {
    if (shouldSendOnEnter(event, state.chatPending || state.composing)) {
      event.preventDefault();
      byId("chat-form").requestSubmit();
    }
  });
  byId("data-form").addEventListener("submit", saveData);
  byId("data-cancel").addEventListener("click", () => { if (!state.dataBusy) { resetDataForm(); notice("data-feedback", "수정을 취소했습니다. 저장값은 변경하지 않았습니다."); } });
  byId("data-rows").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-id]");
    if (!button || button.disabled) return;
    const record = state.data.find((item) => item.id === button.dataset.id);
    if (!record) return;
    if (button.dataset.action === "edit") editRecord(record);
    else if (button.dataset.action === "delete") deleteRecord(record);
  });
  function disconnectAccess() {
    accessToken = "";
    byId("access-token").value = "";
    state.listVersion++;
    state.conversationsLoading = false;
    state.conversations = [];
    byId("conversation-count").textContent = "";
    newConversation();
    notice("conversation-list-state", "접근 토큰을 연결하면 이전 질문을 불러올 수 있습니다.");
    notice("access-status", "연결을 해제했습니다. 토큰과 불러온 질문을 화면에서 지웠습니다.");
    updateControls();
  }
  byId("access-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (accessPending || state.chatPending || state.dataBusy || state.conversationBusy) return;
    const candidate = byId("access-token").value.trim();
    byId("access-token").value = "";
    if (!/^[\x21-\x7e]{32,}$/.test(candidate)) {
      notice("access-status", "공백 없는 영문·숫자·기호 32자 이상의 접근 토큰을 입력하세요.", "error");
      return;
    }
    disconnectAccess();
    accessToken = candidate;
    accessPending = true;
    updateControls();
    notice("access-status", "접근 권한을 확인하고 있습니다. 서버가 쉬고 있었다면 잠시 걸릴 수 있습니다.");
    const ok = await loadConversations();
    accessPending = false;
    if (ok) notice("access-status", "연결됐습니다. 이 탭에서 보호 기능을 사용할 수 있습니다.", "success");
    else { disconnectAccess(); notice("access-status", "연결하지 못했습니다. 접근 토큰과 서버 상태를 확인하세요.", "error"); }
    updateControls();
  });
  byId("access-clear").addEventListener("click", disconnectAccess);
  window.addEventListener("pagehide", () => { accessToken = ""; byId("access-token").value = ""; });
  window.addEventListener("pageshow", (event) => { if (event.persisted) window.location.reload(); });
  const selection = restoreSelection();
  updateControls();
  loadSummary();
  loadData();
  loadConversations().then((ok) => {
    if (ok && selection && state.detailVersion === 0 && !state.chatPending) {
      if (state.conversations.some((item) => item.id === selection)) loadConversation(selection);
      else { persistSelection(null); notice("chat-feedback", "이전에 선택한 질문 기록이 목록에 없습니다. 다른 질문 기록을 선택하거나 새로 시작하세요."); }
    }
  });
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", startApp, { once: true });
  else startApp();
}
