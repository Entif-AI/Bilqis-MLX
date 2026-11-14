"use strict";

const OPERATOR_VIEW = require("../fixtures/operator-view-v1.json");
const { Cp01PythonBroker } = require("./cp01-python-broker.cjs");
const { frameFixturePage } = require("./frame-fixtures.cjs");

function disconnectedStatus() {
  return {
    schemaVersion: "bamf.gui20.cp01-status/v1",
    state: "disconnected",
    protocolVersion: "bilqis.bamf.control-plane/v1",
    serviceLive: false,
    serviceReady: false,
    learnerReady: false,
    learnerActive: null,
  };
}

class AcceptedControlPlaneAdapter {
  constructor({ broker = new Cp01PythonBroker() } = {}) {
    this.broker = broker;
    this.session = Object.freeze({ session: Symbol("gui20-main-session") });
  }

  async connect() {
    let publicStatus;
    try {
      publicStatus = await this.broker.connect();
    } catch (_error) {
      publicStatus = disconnectedStatus();
    }
    return { session: this.session, publicStatus };
  }

  async disconnect(session) {
    this.#requireSession(session);
    try {
      await this.broker.disconnect();
    } catch (_error) {
      // A lost broker is already disconnected from the renderer's perspective.
    }
  }

  async status(session) {
    this.#requireSession(session);
    try {
      return await this.broker.status();
    } catch (_error) {
      return disconnectedStatus();
    }
  }

  async snapshot(session, request) {
    this.#requireSession(session);
    if (request?.schemaVersion === "bamf.gui08.frame-query/v1") return frameFixturePage(request);
    return structuredClone(OPERATOR_VIEW);
  }

  close() {
    this.broker.close();
  }

  #requireSession(session) {
    if (session !== this.session) {
      const error = new Error("BAMF_GUI20_SESSION_INVALID");
      error.code = "BAMF_GUI20_SESSION_INVALID";
      throw error;
    }
  }
}

module.exports = { AcceptedControlPlaneAdapter, disconnectedStatus };
