package ch.routify.controllers;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Controller responsible for handling health check endpoints.
 * This controller provides an endpoint for checking the health of the system.
 * 
 * @author Alexander Eggerth
 * @version 1.0
 */
@RestController
public class HealthController {

    @GetMapping("/health")
    public ResponseEntity<String> health() {
        return ResponseEntity.ok("OK");
    }
}


