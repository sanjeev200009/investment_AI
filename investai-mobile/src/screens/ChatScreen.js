// src/screens/ChatScreen.js
//
// Assistant, v2 "Soft pastel": black user bubbles, white glass answers, lime
// chips for each tool the agent called, and a white round composer that sits
// above the floating tab bar.
import React, { useState, useRef, useCallback } from 'react';
import { View, Text, StyleSheet, FlatList, TextInput, KeyboardAvoidingView, Platform, StatusBar } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import TouchableTick from '../components/TouchableTick';
import { Screen, Header, PillButton, Loading } from '../components/ui';
import api, { refreshSession } from '../api/axiosConfig';
import { streamSSE } from '../api/sse';
import { useT } from '../store/languageStore';
import { palette, fonts, radii } from '../theme/tokens';

const INITIAL_MESSAGES = [];

// Translation keys; t() at render and on send, so the assistant receives the
// question in the user's language.
const ALL_QUICK_ACTIONS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(i => `chat_qa_${i}`);

export default function ChatScreen({ navigation, route }) {
  const { t } = useT();
  const [messages, setMessages] = useState(INITIAL_MESSAGES);
  const [inputText, setInputText] = useState('');
  // The server keeps the conversation (chat_sessions / chat_messages) and feeds
  // it back to the model as memory, but the screen used to start blank on every
  // open, so the user could not see the thread the assistant was continuing.
  const [sessionId, setSessionId] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(true);

  const loadConversation = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const { data: sessions } = await api.get('/chat/sessions', { params: { active_only: true } });
      const current = sessions?.[0];
      if (!current) { setSessionId(null); setMessages([]); return; }
      setSessionId(current.session_id);
      const { data: rows } = await api.get(`/chat/sessions/${current.session_id}/messages`, { params: { limit: 50 } });
      setMessages((rows || []).map(m => ({
        id: `m${m.message_id}`,
        type: m.sender_type === 'user' ? 'user' : 'ai',
        text: m.content,
        tools: [],
      })));
    } catch (_) {
      // History is a convenience; an empty screen still works for a new question.
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  React.useEffect(() => { loadConversation(); }, [loadConversation]);

  // "Ask the assistant" on a stock screen arrives with a ready question. It is
  // placed in the input, not sent, so the user can edit it first.
  React.useEffect(() => {
    const prompt = route?.params?.prompt;
    if (prompt) {
      setInputText(prompt);
      navigation.setParams({ prompt: undefined });
    }
  }, [route?.params?.prompt, navigation]);

  const startNewChat = useCallback(async () => {
    if (abortRef.current) abortRef.current();
    try {
      if (sessionId) await api.delete(`/chat/sessions/${sessionId}`);
      const { data } = await api.post('/chat/sessions');
      setSessionId(data.session_id);
    } catch (_) {
      setSessionId(null);  // the server opens one on the next message
    }
    setMessages([]);
  }, [sessionId]);
  const [quickActions, setQuickActions] = useState([]);

  React.useEffect(() => {
    const shuffled = [...ALL_QUICK_ACTIONS].sort(() => 0.5 - Math.random());
    setQuickActions(shuffled.slice(0, 4));
  }, []);

  // Streaming chat (I-14). The backend's ReAct loop emits SSE events; this
  // screen renders them as they arrive instead of staring at a typing
  // indicator for the 15-30s a full agent round-trip used to take against the
  // documented 3-5s NFR. Tool calls render as activity lines — which also
  // makes the agent's reasoning steps visible, the viva demonstration of the
  // ReAct pattern.
  const abortRef = useRef(null);
  const listRef = useRef(null);
  const [isStreaming, setIsStreaming] = useState(false);

  // Close any open stream when the screen goes away.
  React.useEffect(() => () => { if (abortRef.current) abortRef.current(); }, []);

  const handleSend = useCallback(async (textToSend) => {
    if (!textToSend.trim() || isStreaming) return;

    const userText = textToSend.trim();
    if (textToSend === inputText) setInputText('');

    const now = Date.now();
    const aiId = `${now + 1}`;

    setMessages(prev => [...prev,
      { id: `${now}`, type: 'user', text: userText },
      { id: aiId, type: 'ai', isTyping: true, text: '', tools: [] },
    ]);
    setIsStreaming(true);

    const patchAi = (patch) => setMessages(prev => prev.map(m =>
      m.id === aiId ? { ...m, ...patch } : m));

    const appendToken = (content) => setMessages(prev => prev.map(m =>
      m.id === aiId ? { ...m, isTyping: false, text: (m.text || '') + content } : m));

    const addTool = (tool) => setMessages(prev => prev.map(m =>
      m.id === aiId
        ? { ...m, isTyping: false, tools: [...(m.tools || []), { name: tool, done: false }] }
        : m));

    const finishTool = (tool) => setMessages(prev => prev.map(m => {
      if (m.id !== aiId || !m.tools?.length) return m;
      const tools = [...m.tools];
      for (let i = tools.length - 1; i >= 0; i--) {
        if (tools[i].name === tool && !tools[i].done) { tools[i] = { ...tools[i], done: true }; break; }
      }
      return { ...m, tools };
    }));

    const finish = () => {
      setIsStreaming(false);
      abortRef.current = null;
    };

    const failWith = (text) => {
      setMessages(prev => prev.map(m =>
        m.id === aiId ? { ...m, isTyping: false, text: m.text || text } : m));
      finish();
    };

    // One attempt; on a 401 the access token has expired (they last about an
    // hour), so refresh through the same shared path axios uses and retry once.
    // The stream reads the token itself and bypasses axios's interceptor.
    const start = async (retried) => {
      const token = await AsyncStorage.getItem('token');
      abortRef.current = streamSSE({
        url: '/chat/stream',
        body: sessionId ? { message: userText, session_id: sessionId } : { message: userText },
        token,
        onEvent: (event) => {
          switch (event.type) {
            case 'token':
              if (event.content) appendToken(event.content);
              break;
            case 'tool_start':
              if (event.tool) addTool(event.tool);
              break;
            case 'tool_result':
              if (event.tool) finishTool(event.tool);
              break;
            case 'done':
              patchAi({ isTyping: false });
              // First message of a fresh conversation: the server opened the
              // session, so pick up its id for the messages that follow.
              if (!sessionId) {
                api.get('/chat/sessions', { params: { active_only: true } })
                  .then(({ data }) => { if (data?.[0]) setSessionId(data[0].session_id); })
                  .catch(() => {});
              }
              break;
            case 'error':
              patchAi({
                isTyping: false,
                text: event.detail || t('chat_error_no_answer'),
              });
              break;
            case '__stream_end':
              // Normal completion; anything still marked typing had no text —
              // leave a visible placeholder rather than a blank bubble.
              patchAiIfEmpty();
              finish();
              break;
            default:
              break;
          }
        },
        onError: async (err) => {
          if (err?.status === 401 && !retried) {
            try {
              if (await refreshSession()) return start(true);
            } catch (_) { /* fall through to the error bubble */ }
          }
          failWith(err?.status === 429
            ? t('chat_error_rate_limited')
            : t('chat_error_unreachable'));
        },
      });
    };

    try {
      await start(false);
    } catch (error) {
      failWith(t('chat_error_connect'));
    }

    function patchAiIfEmpty() {
      setMessages(prev => prev.map(m =>
        m.id === aiId && !(m.text || '').trim() && !(m.tools || []).length
          ? { ...m, isTyping: false, text: t('chat_no_response') }
          : m));
    }
  }, [inputText, isStreaming, sessionId]);

  // Room for the floating tab bar (about 74px tall, 12px off the bottom).
  const insets = useSafeAreaInsets();
  const barSpace = 96 + insets.bottom;

  const renderMessage = ({ item }) => {
    if (item.type !== 'ai') {
      return (
        <View
          style={styles.userBubble}
          accessible
          accessibilityLabel={`${t('chat_you')}: ${item.text}`}
        >
          <Text style={[styles.messageText, { color: '#FFFFFF' }]}>{item.text}</Text>
        </View>
      );
    }

    const tools = item.tools || [];
    return (
      <View style={styles.aiGroup}>
        {/* ReAct activity: one chip per tool the agent called, in order,
            turning lime when its result lands. The agent loop made visible. */}
        {tools.length > 0 && (
          <View style={styles.toolRow}>
            {tools.map((tool, i) => (
              <View
                key={`${tool.name}-${i}`}
                style={[styles.toolChip, { backgroundColor: tool.done ? palette.lime : palette.glassSoft }]}
              >
                <MaterialIcons
                  name={tool.done ? 'check' : 'sync'}
                  size={14}
                  color={tool.done ? palette.limeInk : palette.ink}
                />
                <Text style={[styles.toolText, { color: tool.done ? palette.limeInk : palette.ink }]}>
                  {t(tool.done ? 'chat_tool_used' : 'chat_tool_checking').replace('{tool}', tool.name)}
                </Text>
              </View>
            ))}
          </View>
        )}

        {(item.isTyping || item.text) ? (
          <View
            style={styles.aiBubble}
            accessible
            accessibilityLabel={item.isTyping ? t('chat_ai_name') : `${t('chat_ai_name')}: ${item.text}`}
          >
            {item.isTyping ? (
              <View style={styles.typing}>
                <View style={styles.typingDot} />
                <View style={[styles.typingDot, { opacity: 0.6 }]} />
                <View style={[styles.typingDot, { opacity: 0.3 }]} />
              </View>
            ) : (
              <Text style={styles.messageText}>{item.text}</Text>
            )}
          </View>
        ) : null}
      </View>
    );
  };

  const newChatOff = isStreaming || messages.length === 0;

  return (
    <Screen scroll={false} contentStyle={styles.screen}>
      <StatusBar barStyle="dark-content" />
      <View style={styles.headerWrap}>
        <Header
          title={t('chat_title')}
          subtitle={t('chat_subtitle')}
          right={(
            <PillButton
              variant="secondary"
              title={t('chat_new_chat')}
              label={t('chat_new_chat_a11y')}
              onPress={startNewChat}
              disabled={newChatOff}
              style={styles.newChat}
            />
          )}
        />
      </View>

      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
        // iOS: the keyboard covers the tab bar, so drop the room kept for it.
        keyboardVerticalOffset={Platform.OS === 'ios' ? -barSpace : 20}
      >
        <FlatList
          ref={listRef}
          data={messages}
          renderItem={renderMessage}
          onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
          ListEmptyComponent={historyLoading ? <Loading /> : null}
          keyExtractor={item => item.id}
          contentContainerStyle={styles.messageList}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        />

        <View style={[styles.footer, { paddingBottom: barSpace }]}>
          <FlatList
            horizontal
            showsHorizontalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
            data={quickActions}
            renderItem={({ item }) => (
              <TouchableTick
                style={[styles.suggestion, isStreaming && { opacity: 0.5 }]}
                onPress={() => handleSend(t(item))}
                disabled={isStreaming}
                accessibilityRole="button"
              >
                <Text style={styles.suggestionText}>{t(item)}</Text>
              </TouchableTick>
            )}
            keyExtractor={item => item}
            contentContainerStyle={styles.suggestionList}
          />

          <View style={styles.composer}>
            <TextInput
              style={styles.input}
              placeholder={t('chat_input_placeholder')}
              placeholderTextColor={palette.faint}
              accessibilityLabel={t('chat_input_placeholder')}
              value={inputText}
              onChangeText={setInputText}
              maxLength={2000}
              multiline
            />
            <TouchableTick
              style={[styles.sendBtn, isStreaming && { opacity: 0.5 }]}
              onPress={() => handleSend(inputText)}
              disabled={isStreaming}
              accessibilityRole="button"
              accessibilityLabel={t('chat_send_a11y')}
              accessibilityState={{ disabled: isStreaming, busy: isStreaming }}
            >
              <MaterialIcons name="arrow-upward" size={22} color="#FFFFFF" />
            </TouchableTick>
          </View>
          <Text style={styles.disclaimer}>{t('chat_disclaimer')}</Text>
        </View>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const text = { color: palette.ink, fontFamily: fonts.regular };

const styles = StyleSheet.create({
  screen: { paddingHorizontal: 0, paddingBottom: 0, gap: 0 },
  headerWrap: { paddingHorizontal: 20 },
  newChat: { height: 56, paddingHorizontal: 18 },
  messageList: { paddingHorizontal: 20, paddingTop: 24, paddingBottom: 16, gap: 16, flexGrow: 1 },
  userBubble: {
    alignSelf: 'flex-end', maxWidth: '80%', backgroundColor: palette.ink,
    borderRadius: 28, borderBottomRightRadius: 8, paddingHorizontal: 18, paddingVertical: 14,
  },
  aiGroup: { gap: 8, alignItems: 'flex-start' },
  aiBubble: {
    alignSelf: 'stretch', backgroundColor: 'rgba(255,255,255,0.9)',
    borderRadius: radii.xl, borderTopLeftRadius: 8, padding: 20,
  },
  messageText: { ...text, fontSize: 16, lineHeight: 24 },
  toolRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  toolChip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    borderRadius: radii.full, paddingHorizontal: 12, paddingVertical: 6,
  },
  toolText: { fontFamily: fonts.medium, fontSize: 12 },
  typing: { flexDirection: 'row', gap: 5, paddingVertical: 6 },
  typingDot: { width: 8, height: 8, borderRadius: radii.full, backgroundColor: palette.ink },
  footer: { paddingTop: 8, gap: 12 },
  suggestionList: { paddingHorizontal: 20, gap: 8 },
  suggestion: {
    height: 44, justifyContent: 'center', paddingHorizontal: 16,
    borderRadius: radii.full, backgroundColor: 'rgba(255,255,255,0.6)',
  },
  suggestionText: { ...text, fontSize: 13 },
  composer: {
    marginHorizontal: 20, flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: '#FFFFFF', borderRadius: radii.full, padding: 6, paddingLeft: 22,
  },
  input: { ...text, flex: 1, fontSize: 16, minHeight: 50, maxHeight: 120, paddingTop: 14, paddingBottom: 14 },
  sendBtn: {
    width: 52, height: 52, borderRadius: radii.full, backgroundColor: palette.ink,
    alignItems: 'center', justifyContent: 'center',
  },
  disclaimer: { ...text, fontSize: 11, color: palette.muted, textAlign: 'center', paddingHorizontal: 24 },
});
