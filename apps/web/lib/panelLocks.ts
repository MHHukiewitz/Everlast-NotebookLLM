export type PanelBusy = {
  chatBusy: boolean;
  addBusy: boolean;
  researchBusy: boolean;
};

export function panelLocks(state: PanelBusy) {
  return {
    chatSendDisabled: state.chatBusy,
    sourceAddDisabled: state.addBusy,
    sourceResearchDisabled: state.researchBusy,
  };
}
