// Implementation of the photo-API used as example on RESTdesc.org

'use strict'

const _ = require('lodash')
const fs = require('fs-extra')
const bunyan = require('bunyan')
const express = require('express')
const { processenv } = require('processenv')
const fileUpload = require('express-fileupload')

// Instantiate logger
const log = bunyan.createLogger({
  name: 'img_api', // TODO make configurable?
  stream: process.stdout,
  level: processenv('IMG_API_LOGLEVEL', bunyan.INFO),
  serializers: {
    err: bunyan.stdSerializers.err,
    req: bunyan.stdSerializers.req,
    res: function (res) {
      if (!res || !res.statusCode) {
        return res
      }
      return {
        statusCode: res.statusCode,
        headers: res._headers
      }
    }
  }
})

// Read configuration
async function readConfig () {
  const config = {
    listenPort: processenv('IMG_API_PORT', 3000)
  }

  return config
}

// Initialize server
async function init () {
  const cfg = await readConfig()

  // Instantiate express-application and set up middleware-stack
  const app = express()
  app.use(fileUpload())

  // TODO Define routing

  // Start listening to incoming requests
  app.listen(cfg.listenPort, function () {
    log.info(`Listening on port ${cfg.listenPort}`)
  })
}

// Run when executed as module
if (require.main === module) {
  init()
}
