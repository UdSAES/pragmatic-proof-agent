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
    language: processenv('IMG_API_LANG', 'en'),
    tmpDirectory: processenv('IMG_API_TMP', '/tmp'),
    listenPort: processenv('IMG_API_PORT', 3000),
  }

  log.debug({config: config}, 'Instance configuration loaded')

  return config
}

// Describe hypermedia API using RESTdesc
async function n3addImage (req, res) {
  await respondWithNotImplemented(req, res)
}

async function n3getImage (req, res) {
  await respondWithNotImplemented(req, res)
}

async function n3getThumbnail (req, res) {
  await respondWithNotImplemented(req, res)
}

// Define request handlers
async function browseAPI (req, res) {
  await respondWithNotImplemented (req, res)
}

async function addImage (req, res) {
  await respondWithNotImplemented (req, res)
}

async function getImage (req, res) {
  await respondWithNotImplemented (req, res)
}

async function getThumbnail (req, res) {
  await respondWithNotImplemented (req, res)
}

// Properly respond in case of errors
async function sendProblemDetail (res, config) {
  // `config` is a dictionary containing the fields from RFC 7807
  // field `status` is required; `detail`, `type`, `title`, `instance` are optional
  res.set('Content-Type', 'application/problem+json')
  const statusCode = config.status
  res.status(statusCode).json(config)
}

async function respondWithNotImplemented (req, res) {
  await sendProblemDetail(res, {
    title: 'Not Implemented',
    status: 501,
    detail:
      'The request was understood, but the underlying implementation is not available yet.'
  })
  log.info(
    `\`${req.method} ${req.path}\` -> \`501 Not Implemented\``
  )
}

async function respondWithNotFound (req, res) {
  await sendProblemDetail(res, {
    title: 'Not Found',
    status: 404,
    detail: 'The requested resource was not found on this server'
  })
  log.info(
    `\`${req.method} ${req.path}\` -> \`404 Not Found\``
  )
}

// Initialize server
async function init () {
  const cfg = await readConfig()

  // Instantiate express-application and set up middleware-stack
  const app = express()
  app.use(fileUpload())

  // Construct resource paths
  const lang = cfg.language
  const resourceNames = {
    images: {
      en: 'images',
      de: 'bilder',
      fr: 'photos'
    },
    thumbnail: {
      en: 'thumbnail',
      de: 'miniaturbild',
      fr: 'miniature'
    }
  }

  const collectionOfImages = `/${resourceNames.images[lang]}`
  const specificImage = `${collectionOfImages}/:imageId`
  const thumbnail = `${specificImage}/${resourceNames.thumbnail[lang]}`

  // Define routing
  app.get('/', browseAPI)

  app.options(collectionOfImages, n3addImage)
  app.post(collectionOfImages, addImage)

  app.options(specificImage, n3getImage)
  app.get(specificImage, getImage)

  app.options(thumbnail, n3getThumbnail)
  app.get(thumbnail, getThumbnail)

  // Send 404 as reaction to all other requests
  app.use((req, res, next) => respondWithNotFound(req, res, next))

  // Start listening to incoming requests
  app.listen(cfg.listenPort, function () {
    log.info(`Listening on port ${cfg.listenPort}`)
  })
}

// Run when executed as module
if (require.main === module) {
  init()
}
