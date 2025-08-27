    def reconnect_process(self, session_id: str, process_id: int) -> bool:
        """
        Reconnect to an existing process.
        
        Args:
            session_id: Session identifier
            process_id: Process ID to reconnect to
            
        Returns:
            True if reconnection successful
        """
        try:
            # Verify process is still alive
            try:
                os.kill(process_id, 0)
            except (OSError, ProcessLookupError):
                logger.warning(f"Process {process_id} is no longer alive")
                return False
            
            # Store process information
            self.active_processes[session_id] = {
                'pid': process_id,
                'command': 'reconnected',
                'started_at': datetime.now(),
                'status': 'running',
                'reconnected': True
            }
            
            # Start monitoring thread
            self._start_process_monitor(session_id, process_id)
            
            logger.info(f"Reconnected to process {process_id} for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reconnect to process {process_id}: {e}")
            return False

