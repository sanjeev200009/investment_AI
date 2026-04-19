import React, { useState } from 'react';
import { View, Text, StyleSheet, FlatList, TextInput, TouchableOpacity, KeyboardAvoidingView, Platform, SafeAreaView, Image, StatusBar } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useAppTheme } from '../hooks/useAppTheme';

const INITIAL_MESSAGES = [
  {
    id: '1',
    type: 'ai',
    name: 'AI Assistant',
    text: "Hello! I'm your AI Investment Assistant. How can I help you today? You can ask me about stocks, market trends, or analyze your portfolio.",
  },
  {
    id: '2',
    type: 'user',
    name: 'You',
    text: 'What are the top performing tech stocks this quarter?',
  },
  {
    id: '3',
    type: 'ai',
    name: 'AI Assistant',
    text: 'Based on current market data, the top-performing tech stocks this quarter include companies in the semiconductor and AI sectors. Here are the top 3:',
    list: [
      { id: 'l1', bold: 'Innovate Inc. (INV)', text: ': +25.4%' },
      { id: 'l2', bold: 'QuantumChip (QTC)', text: ': +22.1%' },
      { id: 'l3', bold: 'CloudNet (CLD)', text: ': +19.8%' },
    ],
    actions: [
      { id: 'a1', label: 'Show reasoning', icon: 'expand-more' },
      { id: 'a2', label: 'View full analysis', icon: 'chevron-right' }
    ]
  }
];

const QUICK_ACTIONS = [
  'Top stocks today',
  'What is P/E ratio?',
  'Analyze my portfolio',
  'Market outlook'
];

export default function ChatScreen({ navigation }) {
  const theme = useAppTheme();
  const [messages, setMessages] = useState(INITIAL_MESSAGES);
  const [inputText, setInputText] = useState('');

  // Explicitly derive colors from theme for maximum reactivity
  const isDark = theme.isDark;
  const colors = {
    primary: theme.colors.primary,
    background: theme.colors.background,
    surface: theme.colors.surface,
    textPrimary: theme.colors.textPrimary,
    textSecondary: theme.colors.textSecondary,
    border: theme.colors.border,
    aiBubble: isDark ? '#1D232A' : '#F3F4F6',
    userBubble: isDark ? '#192C48' : theme.colors.primary,
    userText: isDark ? '#FFFFFF' : '#FFFFFF', // Both white for contrast on dark bubbles
    aiText: isDark ? '#D1D5DB' : '#374151',
    inputBg: isDark ? '#1D232A' : '#F9FAFB',
  };

  const renderMessage = ({ item }) => {
    const isAI = item.type === 'ai';

    if (isAI) {
      return (
        <View style={styles.aiMessageGroup}>
          <View style={[styles.aiAvatar, { backgroundColor: colors.aiBubble }]}>
            <MaterialIcons name="smart-toy" size={24} color={colors.primary} />
          </View>
          <View style={styles.aiContentGroup}>
            <Text style={[styles.messageName, { color: colors.textPrimary }]}>{item.name}</Text>
            <View style={[styles.aiBubble, { backgroundColor: colors.aiBubble }]}>
              {item.isTyping ? (
                <View style={styles.typingContainer}>
                  <View style={[styles.typingDot, { backgroundColor: colors.primary }]} />
                  <View style={[styles.typingDot, { backgroundColor: colors.primary, opacity: 0.6 }]} />
                  <View style={[styles.typingDot, { backgroundColor: colors.primary, opacity: 0.3 }]} />
                </View>
              ) : (
                <>
                  <Text style={[styles.messageText, { color: colors.aiText }]}>{item.text}</Text>

                  {item.list && (
                    <View style={styles.listContainer}>
                      {item.list.map(li => (
                        <View key={li.id} style={styles.listItem}>
                          <View style={[styles.dot, { backgroundColor: colors.textSecondary }]} />
                          <Text style={[styles.listItemText, { color: colors.aiText }]}>
                            <Text style={{ fontWeight: '700', color: colors.textPrimary }}>{li.bold}</Text>
                            {li.text}
                          </Text>
                        </View>
                      ))}
                    </View>
                  )}

                  {item.actions && (
                    <View style={styles.innerActions}>
                      {item.actions.map(action => (
                        <TouchableOpacity key={action.id} style={[styles.innerActionBtn, { borderColor: colors.border }]}>
                          <Text style={[styles.innerActionLabel, { color: colors.primary }]}>{action.label}</Text>
                          <MaterialIcons name={action.icon} size={18} color={colors.primary} />
                        </TouchableOpacity>
                      ))}
                    </View>
                  )}
                </>
              )}
            </View>
          </View>
        </View>
      );
    }

    return (
      <View style={styles.userMessageGroup}>
        <View style={styles.userContentGroup}>
          <Text style={[styles.messageName, { color: colors.textSecondary, textAlign: 'right' }]}>{item.name}</Text>
          <View style={[styles.userBubble, { backgroundColor: colors.userBubble }]}>
            <Text style={[styles.messageText, { color: colors.userText }]}>{item.text}</Text>
          </View>
        </View>
        <Image
          source={{ uri: "https://lh3.googleusercontent.com/aida-public/AB6AXuCk3JbinKI6zRcK2m-0nSartwmhlQoUPvH6r5NQzc4SXz_C_XsvWHHuycDOjn1owP2KuEChQKakcOxqi7Rh6ORyrQ2DdloG16B0GMV1_aw4-eBShI7oMjRP_n3RerZNZ2xjX1349a8wVS5ziQ0RvZYggcE2b_rsJyq3fKZ8JNEbiFIOkESvPhAhbymxRjDiYKLxjg7HVTrcMi0gr72Nqc2ZkqpJ9kMvHQPATnoRswcRVhZnMjrugf2SdKTvKyjTndUMfVAf0djpl3k" }}
          style={styles.userAvatar}
        />
      </View>
    );
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
      <StatusBar barStyle={isDark ? 'light-content' : 'dark-content'} />
      {/* Header */}
      <View style={[styles.header, { borderBottomColor: colors.border }]}>
        <View style={styles.headerIcon}>
          <MaterialIcons name="insights" size={28} color={colors.textPrimary} />
        </View>
        <Text style={[styles.headerTitle, { color: colors.textPrimary }]}>Investment Assistant</Text>
        <TouchableOpacity style={styles.settingsBtn}>
          <MaterialIcons name="settings" size={24} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>

      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.content}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 20}
      >
        <FlatList
          data={messages}
          renderItem={renderMessage}
          keyExtractor={item => item.id}
          contentContainerStyle={styles.messageList}
          showsVerticalScrollIndicator={false}
        />

        {/* Quick Actions Footer */}
        <View style={[styles.footer, { backgroundColor: colors.background }]}>
          <FlatList
            horizontal
            showsHorizontalScrollIndicator={false}
            data={QUICK_ACTIONS}
            renderItem={({ item }) => (
              <TouchableOpacity style={[styles.quickActionChip, { backgroundColor: colors.aiBubble }]}>
                <Text style={[styles.quickActionText, { color: colors.textSecondary }]}>{item}</Text>
              </TouchableOpacity>
            )}
            keyExtractor={item => item}
            contentContainerStyle={styles.quickActionsList}
          />

          {/* Input Area */}
          <View style={[styles.inputArea, { borderTopWidth: 1, borderTopColor: colors.border }]}>
            <View style={[styles.inputWrapper, { backgroundColor: colors.inputBg, borderColor: colors.border }]}>
              <TextInput
                style={[styles.input, { color: colors.textPrimary }]}
                placeholder="Ask about a stock or trend..."
                placeholderTextColor={colors.textSecondary}
                value={inputText}
                onChangeText={setInputText}
              />
              <TouchableOpacity style={styles.micBtn}>
                <MaterialIcons name="mic" size={24} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            <TouchableOpacity
              style={[styles.sendBtn, { backgroundColor: colors.primary }]}
              onPress={() => {
                if (inputText.trim()) {
                  const newMessage = {
                    id: Date.now().toString(),
                    type: 'user',
                    name: 'You',
                    text: inputText.trim()
                  };
                  setMessages([...messages, newMessage]);
                  setInputText('');
                }
              }}
            >
              <MaterialIcons name="send" size={24} color="#FFFFFF" />
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
  },
  headerIcon: {
    marginRight: 12,
  },
  headerTitle: {
    flex: 1,
    fontSize: 18,
    fontWeight: '700',
    letterSpacing: -0.5,
  },
  settingsBtn: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  content: {
    flex: 1,
  },
  messageList: {
    padding: 16,
    gap: 24,
  },
  aiMessageGroup: {
    flexDirection: 'row',
    gap: 12,
  },
  aiAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    shrink: 0,
  },
  aiContentGroup: {
    flex: 1,
    gap: 4,
  },
  aiBubble: {
    padding: 12,
    borderRadius: 12,
    borderTopLeftRadius: 0,
    gap: 12,
  },
  userMessageGroup: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 12,
  },
  userContentGroup: {
    flex: 1,
    alignItems: 'flex-end',
    gap: 4,
  },
  userBubble: {
    padding: 12,
    borderRadius: 12,
    borderBottomRightRadius: 0,
  },
  userAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    shrink: 0,
  },
  messageName: {
    fontSize: 13,
    fontWeight: '700',
  },
  messageText: {
    fontSize: 15,
    lineHeight: 22,
  },
  listContainer: {
    gap: 8,
    paddingLeft: 4,
  },
  listItem: {
    flexDirection: 'row',
    gap: 8,
  },
  dot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    marginTop: 8,
  },
  listItemText: {
    fontSize: 14,
    lineHeight: 20,
  },
  innerActions: {
    gap: 8,
    paddingTop: 4,
  },
  innerActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 10,
    borderRadius: 6,
    borderWidth: 1,
  },
  innerActionLabel: {
    fontSize: 14,
    fontWeight: '600',
  },
  typingContainer: {
    flexDirection: 'row',
    gap: 4,
    paddingVertical: 4,
  },
  typingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  footer: {
    paddingBottom: Platform.OS === 'ios' ? 0 : 12,
  },
  quickActionsList: {
    paddingHorizontal: 16,
    paddingBottom: 12,
    gap: 8,
  },
  quickActionChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  quickActionText: {
    fontSize: 14,
    fontWeight: '500',
  },
  inputArea: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    gap: 8,
  },
  inputWrapper: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 999,
    borderWidth: 1,
    paddingLeft: 16,
    paddingRight: 8,
    height: 48,
  },
  input: {
    flex: 1,
    fontSize: 16,
    height: '100%',
  },
  micBtn: {
    padding: 8,
  },
  sendBtn: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
