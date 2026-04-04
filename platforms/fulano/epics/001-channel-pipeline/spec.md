# Feature Specification: Channel Pipeline

**Feature Branch**: `epic/fulano/001-channel-pipeline`
**Created**: 2026-04-04
**Status**: Draft
**Input**: User description: "Receive and respond to WhatsApp messages with smart routing for individual and group conversations"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receive and echo individual messages (Priority: P1)

A customer sends a WhatsApp message to the business number. The system receives the message, identifies it as an individual conversation, and sends back an echo of the received text. This validates the entire message pipeline end-to-end.

**Why this priority**: This is the foundational flow — without receiving and responding to a single message, nothing else works. Every subsequent epic (AI agents, persistence, handoff) depends on this path being functional.

**Independent Test**: Send a WhatsApp message to the connected number and verify an echo response arrives within seconds.

**Acceptance Scenarios**:

1. **Given** a connected WhatsApp number, **When** a customer sends a text message, **Then** the system receives it and sends back an echo containing the original text.
2. **Given** a connected WhatsApp number, **When** a customer sends a media message (image, audio, video, document), **Then** the system receives it and responds with a text acknowledgment.
3. **Given** a message sent by the bot itself, **When** the system receives the webhook, **Then** it ignores the message (no echo loop).

---

### User Story 2 - Smart routing for group messages with @mention (Priority: P1)

A participant in a WhatsApp group mentions the agent (via phone number or keyword). The system detects the mention, treats it as an active request, and sends an echo response to the group. When no mention is present, the system observes silently (saves to log) without responding.

**Why this priority**: Group AI is the core competitive moat. The ability to distinguish "respond" vs "observe" in groups is essential — without it, the agent either spams groups or ignores them entirely.

**Independent Test**: Send a message with @mention in a group and verify echo response; send a message without @mention and verify no response.

**Acceptance Scenarios**:

1. **Given** a group where the agent is a participant, **When** a member sends a message mentioning the agent, **Then** the system responds with an echo in the group.
2. **Given** a group where the agent is a participant, **When** a member sends a message without mentioning the agent, **Then** the system logs the message but does NOT respond.
3. **Given** a group where the agent is a participant, **When** a member join/leave event occurs, **Then** the system logs the event but does NOT respond.

---

### User Story 3 - Debounce rapid messages (Priority: P2)

A customer types multiple short messages in quick succession (common WhatsApp behavior). Instead of responding to each individually, the system groups them within a short time window and processes them as a single batch before responding once.

**Why this priority**: Without debounce, the agent responds 3 times to someone who types "Hi" / "I need help" / "with my order" in rapid succession — creating a poor user experience and wasting resources.

**Independent Test**: Send 3 messages within 3 seconds and verify only one response is returned containing all message content.

**Acceptance Scenarios**:

1. **Given** a customer sends 3 messages within 3 seconds, **When** the debounce window expires, **Then** the system processes all messages as one batch and sends a single echo response.
2. **Given** a customer sends a message and waits more than 3 seconds, **When** the debounce window expires, **Then** the system responds to that single message normally.
3. **Given** two different customers send messages simultaneously, **When** debounce windows expire, **Then** each customer receives their own independent response.

---

### User Story 4 - System health monitoring (Priority: P3)

An operator or monitoring tool checks whether the messaging service is running and healthy. The system exposes a health endpoint that confirms operational status.

**Why this priority**: Necessary for deployment and operations, but not user-facing functionality.

**Independent Test**: Call the health endpoint and verify a success response.

**Acceptance Scenarios**:

1. **Given** the service is running, **When** the health endpoint is called, **Then** it returns a success status.
2. **Given** the service is not connected to required dependencies, **When** the health endpoint is called, **Then** it returns a degraded or error status.

---

### Edge Cases

- What happens when the WhatsApp provider sends a malformed or unexpected payload? → System logs the error and returns a success status to avoid retries flooding the system.
- What happens when the same message is delivered twice (duplicate webhook)? → System handles idempotently — processes once, ignores duplicates based on message ID.
- What happens when the messaging provider is temporarily unavailable for sending? → System logs the failure for retry; does not crash or lose the received message context.
- What happens when a group event (member join/leave) arrives without a text body? → System classifies as group event and logs silently.
- What happens when @mention detection receives varied formats (phone JID, keywords like "@fulano", "@resenhai")? → System uses case-insensitive matching supporting multiple mention formats.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST receive incoming WhatsApp messages via webhook and acknowledge receipt immediately.
- **FR-002**: System MUST classify each incoming message into exactly one of 5 routes: individual support, group with mention (respond), group without mention (observe only), group event (observe only), or ignore (self-sent messages).
- **FR-003**: System MUST detect @mentions using case-insensitive matching against the agent's phone identifier and configured keywords (e.g., "@resenhai", "@fulano").
- **FR-004**: System MUST ignore messages sent by itself to prevent echo loops.
- **FR-005**: System MUST aggregate rapid sequential messages from the same sender within a configurable time window (default 3 seconds) and process them as a single batch.
- **FR-006**: System MUST send an echo response for individual messages and group messages with @mention.
- **FR-007**: System MUST log group messages without @mention and group events without sending any response.
- **FR-008**: System MUST parse incoming message payloads supporting at minimum: text, extended text, image, document, video, audio, sticker, contact, and location message types.
- **FR-009**: System MUST support sending text responses and media responses through the messaging provider.
- **FR-010**: System MUST expose a health check endpoint that reports service operational status.
- **FR-011**: System MUST handle duplicate message deliveries idempotently (process once per unique message ID).
- **FR-012**: System MUST handle malformed payloads gracefully — log the error and return success to prevent provider retries.

### Key Entities

- **Message**: An incoming communication from a WhatsApp user. Key attributes: unique message ID, sender phone, sender name, text content, media type, media reference, timestamp, group association, mention list, self-sent flag.
- **Conversation**: A logical thread of messages between the agent and one sender (or one group). Identified by phone number (individual) or group ID (group).
- **Route**: The classification result for a message — determines whether the system responds, observes, or ignores.
- **Message Batch**: A set of rapid sequential messages from the same sender, aggregated by the debounce mechanism into a single processing unit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Individual WhatsApp messages receive an echo response within 5 seconds of being sent.
- **SC-002**: Group messages with @mention receive an echo response; group messages without @mention produce zero responses (100% routing accuracy across 5 message types).
- **SC-003**: When a user sends 3+ messages within 3 seconds, the system responds exactly once with aggregated content.
- **SC-004**: The health endpoint responds successfully when the service is operational.
- **SC-005**: The system passes 12+ automated tests covering all 5 routing paths, debounce behavior, and message parsing.
- **SC-006**: The system handles malformed payloads and duplicate messages without crashing or producing incorrect responses.
- **SC-007**: The service starts and runs with all dependencies (messaging provider, message buffer) without manual intervention via container orchestration.

## Assumptions

- The WhatsApp messaging provider (Evolution API) is pre-configured and accessible — this epic does not cover provider setup or account registration.
- No AI/LLM processing in this epic — all responses are simple echo replies. Intelligent responses come in epic 002.
- No database persistence in this epic — message logging is to application logs only. Database storage comes in epic 002.
- The debounce buffer requires a Redis-compatible service running alongside the application.
- Media messages (images, audio, etc.) are acknowledged with a text response — the system does not process or transform media content in this epic.
- The first client (ResenhAI) is the only tenant during this epic — multi-tenant isolation is not required yet.
- Webhook processing is synchronous in this epic — asynchronous worker queues come in epic 002.
- The @mention keyword list is configured at startup and does not change at runtime in this epic.
